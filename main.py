import os
import requests  # 이 줄이 반드시 있어야 합니다!
from Bio import Entrez
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import random # 파일 최상단에 추가

# 환경 변수 및 설정
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PW = os.getenv('GMAIL_PASSWORD')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')

# [수정] 받는 사람 이메일 주소들을 리스트로 관리하세요.
#RECEIVER_EMAILS = [GMAIL_USER, "chocosando@daum.net", "agn70@yuhs.ac", "reanhea55@yuhs.ac", "classic0610@yuhs.ac", "andrew0668@yuhs.ac", "sando@yuhs.ac", "jaywony@gmail.com", "jjdragon112@gmail.com", "leesw1@gmail.com", "drchoi01@snu.ac.kr"] 
RECEIVER_EMAILS = [GMAIL_USER] 


def get_latest_paper_details():
    Entrez.email = GMAIL_USER

    # journals = (
    #     '("Radiology"[Journal] OR "Radiology. Artificial intelligence"[Journal] OR '
    #     '"Lancet Digital Health"[Journal] OR "European Radiology"[Journal] OR '
    #     '"Skeletal radiology"[Journal] OR "AJR. American journal of roentgenology"[Journal]) OR ' 
    #     '"Korean Journal of radiology"[Journal] OR "European journal of Radiology"[Journal]) OR ' 
    #     '"Scientific Reports"[Journal] OR "European journal of Radiology"[Journal]) OR ' 
    # )
    journals = [
        "Radiology", "Radiology. Artificial intelligence", "Lancet Digital Health",
        "European Radiology", "Skeletal radiology", "AJR. American journal of roentgenology",
        "Korean Journal of radiology", "European journal of Radiology", "Scientific Reports",
        "Nature Medicine", "Nature Communications", "Lancet", "Spine", "The Spine Journal",
        "AJNR. American journal of neuroradiology", "Neuroradiology", "Bone & joint journal",
        "PLoS ONE", "JAMA"
    ]

    # topics = '("Musculoskeletal System"[Mesh] OR "Artificial Intelligence"[Mesh] OR "Deep Learning"[Mesh])'
    topics = '("Spine"[Mesh] OR "Spinal Cord"[Mesh] OR "Spondylosis"[Mesh] OR "Intervertebral Disc"[Mesh] OR "Spinal Diseases"[Mesh] OR "Vertebrae"[Title/Abstract])'

    # 최신성(pub_date)을 기준으로 검색하거나, 관련도순 검색 결과 중 상위권을 후보로 둠
    query = f"{journals} AND {topics} AND (2024:2030[pdat])"
    # [개선] hasabstract[Filter] 추가: 초록이 있는 논문만 검색
#    query = f"({journals})AND hasabstract[Filter] AND \"last 60 days\"[dp]"
    
    # [수정] retmax를 10으로 늘려 후보군을 많이 확보합니다.
    handle = Entrez.esearch(db="pubmed", term=query, sort="relevance", retmax=100)
    record = Entrez.read(handle)
    id_list = record["IdList"]
    
    if not id_list:
        # 백업 쿼리: 최근 7일간의 Radiology 저널 논문 5개
        query_fallback = '"Radiology"[Journal] AND "last 90 days"[dp]'
        handle = Entrez.esearch(db="pubmed", term=query_fallback, sort="relevance", retmax=5)
        record = Entrez.read(handle)
        id_list = record["IdList"]

    if not id_list:
        return None
    
    # [핵심] 검색 결과 리스트에서 무작위로 1개를 선택합니다.
    # 이렇게 하면 매일 실행될 때마다 상위 10개 중 다른 논문이 뽑힐 확률이 높습니다.
    pmid = random.choice(id_list)
    
    print(f"Selected PMID: {pmid} from candidates: {id_list}")
    
    # 상위 5개 중 가장 적합한 첫 번째 논문 상세 정보 가져오기
    pmid = id_list[0]
    fetch_handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
    records = Entrez.read(fetch_handle)
    article_data = records['PubmedArticle'][0]
    medline = article_data['MedlineCitation']['Article']
    
    title = medline.get('ArticleTitle', 'No Title')
    abstract_list = medline.get('Abstract', {}).get('AbstractText', [])
    abstract = " ".join([str(text) for text in abstract_list])
    
    authors = [f"{auth.get('LastName', '')} {auth.get('Initials', '')}" for auth in medline.get('AuthorList', [])]
    author_text = ", ".join(authors) if authors else "Unknown"
    
    doi = "N/A"
    for aid in article_data['PubmedData'].get('ArticleIdList', []):
        if aid.attributes.get('IdType') == 'doi':
            doi = str(aid)
            break
    
    journal = medline['Journal'].get('Title', 'Unknown Journal')

    try:
        # 논문 메타데이터 접근
        article = fetch_record['PubmedArticle'][0]['MedlineCitation']['Article']
        pmid = fetch_record['PubmedArticle'][0]['MedlineCitation']['PMID']
        
        # 1. 저자명 추출
        authors_list = []
        if 'AuthorList' in article:
            for auth in article['AuthorList']:
                last_name = auth.get('LastName', '')
                initials = auth.get('Initials', '')
                authors_list.append(f"{last_name} {initials}".strip())
        authors_str = ", ".join(authors_list[:5]) + (" et al." if len(authors_list) > 5 else "")

        # 2. 발행 날짜 추출 (핵심: KeyError 방지)
        pub_date_info = article['Journal']['JournalIssue']['PubDate']
        year = pub_date_info.get('Year', '')
        month = pub_date_info.get('Month', '')
        day = pub_date_info.get('Day', '')
        
        # 만약 Year가 없다면 MedlineDate 필드 확인 (2026 Spring 같은 형식)
        if not year:
            year = pub_date_info.get('MedlineDate', 'Date N/A')
            
        date_str = f"{year} {month} {day}".strip()

        # 3. 데이터 딕셔너리 생성 (여기서 모든 키를 확실히 정의)
        return {
            'title': article.get('ArticleTitle', 'Title N/A'),
            'abstract': abstract, # 기존에 추출한 abstract 변수
            'journal': article['Journal'].get('Title', 'Journal N/A'),
            'date': date_str if date_str else "Date N/A", # 여기서 'date' 키를 확실히 생성
            'authors': authors_str if authors_str else "Author N/A",
            'pubmed_url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        }
    except Exception as e:
        print(f"Error parsing paper details: {e}")
        return None

    
    return {
        "title": title, "abstract": abstract, "authors": author_text,
        "abstract": abstract, # 기존에 추출한 abstract 변수
        "journal": journal, "pmid": pmid, "doi": doi,
        "date": date_str if date_str else "Date N/A", # 여기서 'date' 키를 확실히 생성
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": f"https://doi.org/{doi}" if doi != "N/A" else "#"
    }


def summarize_and_translate(abstract):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    
    # [개선] 분량을 2배로 늘리고 상세 지표를 포함하는 심층 프롬프트
    prompt = f"""
    You are an expert Musculoskeletal Radiologist and Medical Scientist (M.D.-Ph.D.). 
    Analyze the provided abstract in great detail for a specialist-level report.
    
    ### 1. 제목: {info['title']}
    ### 2. 저널 및 날짜: {info['journal']} | 발행일: {info['date']}
    ### 3. 저자: {info['authors']}
    
    # [Output Format]
    # 1. Title: {info['title']}
    # 2. Journal & Date: {info['journal']} | Published: {info.get('date', 'N/A')}
    # 3. Authors: {info.get('authors', 'N/A')}
    
    [Guidelines]
    1. Expand the content to be twice as detailed as a standard summary.
    2. Write in Korean, but ALWAYS include key technical and medical terms in English brackets [English Term].
    3. Ensure the summary covers:
       - 서론: 연구의 배경과 가설을 상세히 기술.
       - 방법: 환자 군[Cohort], 모델 구조[Architecture], 학습 방법[Training] 등 포함.
       - 결과: 구체적인 수치[Numerical values], 신뢰구간[CI], 유의수준[p-value]을 반드시 포함.
       - 고찰: 실제 판독 현장에서의 의의와 기대 효과.
       - 한계점: 초록에서 언급된 제약 사항 기술.

    Abstract to analyze: {info['abstract']}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o", 
        messages=[
            {"role": "system", "content": "You are a senior academic researcher providing in-depth radiology paper reviews."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

    

def send_mail(info, content, receiver):
    html_content = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
            <h2 style="color: #0071bc; border-bottom: 2px solid #0071bc; padding-bottom: 10px;">Spine Radiology Update</h2>
            <h3 style="color: #2c3e50;">{info['title']}</h3>
            <p style="font-size: 0.9em; color: #555;"><strong>Authors:</strong> {info['authors']}<br>
            <strong>Journal:</strong> {info['journal']}</p>
            
            <div style="background-color: #f0f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="margin-top: 0; color: #004a99;">🔬 AI Summary & Translation</h4>
                <div style="white-space: pre-wrap;">{content}</div>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{info['pubmed_url']}" style="background-color: #0071bc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">PubMed 보기</a>
                <a href="{info['doi_url']}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-left: 10px;">DOI 원문보기</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['Subject'] = f"[추영 Daily]{info['title'][:50]}..."
    msg['From'] = GMAIL_USER
    msg['To'] = receiver
    msg.attach(MIMEText(html_content, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PW)
        server.send_message(msg)

def send_telegram_message(info, content):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("Telegram credentials missing.")
        return

    # 텔레그램용 메시지 구성 (HTML 마크업 활용)
    # <br> 대신 \n을 사용하며, <b>, <i> 태그만 지원됩니다.
    text = f"<b>[Daily Spine Radiology]</b>\n\n"
    text += f"<b>{info['title']}</b>\n\n"
    text += f"<i>{info['journal']} ({info['pmid']})</i>\n\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"{content}\n"
    text += f"━━━━━━━━━━━━━━━\n\n"
    text += f"🔗 <a href='{info['pubmed_url']}'>PubMed 보기</a>"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    response = requests.post(url, json=payload)
    return response.status_code


if __name__ == "__main__":
    info = get_latest_paper_details()
    if info:
        content = summarize_and_translate(info['abstract'])
        
        # 1. 이메일 발송 (기존 로직)
        for email in RECEIVER_EMAILS:
            try:
                send_mail(info, content, email)
                print(f"Email success: {email}")
            except Exception as e:
                print(f"Email failed: {e}")
        
        # 2. 텔레그램 발송 (추가된 로직)
        print("Attempting to send Telegram message...") # 로그 확인용 문구
        try:
#            status = send_telegram_message(info, content)
            if status == 200:
                print("Telegram success!")
        except Exception as e:
            print(f"Telegram failed: {e}")
    else:
        print("No papers found.")

