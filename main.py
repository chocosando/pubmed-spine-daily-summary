import os
import requests
from Bio import Entrez
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
from email.header import Header

# 환경 변수 및 설정
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PW = os.getenv('GMAIL_PASSWORD')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

#RECEIVER_EMAILS = [GMAIL_USER, "chocosando@daum.net", "agn70@yuhs.ac", "reanhea55@yuhs.ac", "classic0610@yuhs.ac", "andrew0668@yuhs.ac", "sando@yuhs.ac", "jaywony@gmail.com", "jjdragon112@gmail.com", "leesw1@gmail.com", "drchoi01@snu.ac.kr", "chung@amc.seoul.kr"] 
RECEIVER_EMAILS = [GMAIL_USER]  

def get_latest_paper_details():
    Entrez.email = GMAIL_USER
    
    # journal_list = [
    #     "Radiology", "Radiology. Artificial intelligence", "Lancet Digital Health",
    #     "European Radiology", "Skeletal radiology", "AJR. American journal of roentgenology",
    #     "Korean Journal of radiology", "European journal of Radiology", "Scientific Reports",
    #     "Nature Medicine", "Nature Communications", "Lancet", "Spine", "The Spine Journal",
    #     "AJNR. American journal of neuroradiology", "Neuroradiology", "Bone & joint journal",
    #     "PLoS ONE", "JAMA"
    # ]

    # 1 [핵심 변경] JCR Radiology 카테고리 전체를 아우르는 검색 필터
    radiology_all_jcr = '("Radiology"[Journal] OR "Diagnostic Imaging"[Journal] OR "Nuclear Medicine"[Journal] OR "Medical Imaging"[Journal])'
    # 2 Spine 관련 핵심 키워드 (MSK Radiologist 전문성 유지)
    spine_topics = '("Spine"[Mesh] OR "Spinal Cord"[Mesh] OR "Spondylosis"[Mesh] OR "Intervertebral Disc"[Mesh] OR "Spinal Diseases"[Mesh] OR "Vertebrae"[Title/Abstract])'
    # 3 nature 계열 + SCI/SCIE급 고퀄리티 필터 (Review나 Case Report 제외 가능)
    nature_filter = '("Nature"[Journal] OR "Nature"[Title/Abstract])'

    # 기존 쿼리에 결합 예시
    query = f"({radiology_all_jcr} OR {nature_filter}) AND {spine_topics} AND hasabstract[Filter] AND (2025:2030[pdat])"
    

    try:
        handle = Entrez.esearch(db="pubmed", term=query, sort="relevance", retmax=20)
        record = Entrez.read(handle)
        id_list = record.get("IdList", [])

        if not id_list:
            return None
        
        # 무작위 선택
        pmid = random.choice(id_list)
        
        fetch_handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
        fetch_record = Entrez.read(fetch_handle)
        article_data = fetch_record['PubmedArticle'][0]
        medline = article_data['MedlineCitation']['Article']
        
        # 1. 초록 추출
        abstract_list = medline.get('Abstract', {}).get('AbstractText', [])
        abstract = " ".join([str(text) for text in abstract_list])
        
        # 2. 저자 추출 (최대 5명)
        authors_list = []
        if 'AuthorList' in medline:
            for auth in medline['AuthorList']:
                authors_list.append(f"{auth.get('LastName', '')} {auth.get('Initials', '')}".strip())
        authors_str = ", ".join(authors_list[:5]) + (" et al." if len(authors_list) > 5 else "")
        
        # 3. 날짜 추출
        pub_date_info = medline['Journal']['JournalIssue']['PubDate']
        year = pub_date_info.get('Year', pub_date_info.get('MedlineDate', 'N/A'))
        month = pub_date_info.get('Month', '')
        day = pub_date_info.get('Day', '')
        date_str = f"{year} {month} {day}".strip()

        # 4. DOI 추출
        doi = "N/A"
        for aid in article_data['PubmedData'].get('ArticleIdList', []):
            if aid.attributes.get('IdType') == 'doi':
                doi = str(aid)
                break

        return {
            "title": medline.get('ArticleTitle', 'No Title'),
            "abstract": abstract,
            "authors": authors_str,
            "journal": medline['Journal'].get('Title', 'Unknown Journal'),
            "date": date_str,
            "pmid": pmid,
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "doi_url": f"https://doi.org/{doi}" if doi != "N/A" else "#"
        }
    except Exception as e:
        print(f"Error parsing paper details: {e}")
        return None

def summarize_and_translate(info):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    
    # [수정] 요청하신 줄바꿈 포맷 반영
    prompt = f"""
    You are an expert Musculoskeletal Radiologist (M.D.-Ph.D.). 
    Analyze the provided abstract in great detail for a specialist-level report.
    

    ---

    [Guidelines]
    1. Expand the content to be twice as detailed as a standard summary.
    2. Write in Korean, but ALWAYS include key technical and medical terms in [English Term].
    3. Structure: 서론 및 방법, 결과, 고찰 및 한계점.

    Abstract to analyze: {info['abstract']}
    """

    # 1. 제목: {info['title']}
    # 2. 저널 및 날짜: {info['journal']} | 발행일: {info['date']}
    # 3. 저자: {info['authors']}
#    3. Structure: 제목, 저널 및 날짜, 서론[Introduction], 방법[Methods], 결과[Results], 고찰[Discussion], 한계점[Limitations].

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a senior academic researcher providing in-depth radiology reviews."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

def send_mail(info, content, receiver):
    # AI 요약 내용의 줄바꿈(\n)을 HTML 줄바꿈(<br>)으로 변환
    formatted_content = content.replace("\n", "<br>")
    
    html_content = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 700px; margin: auto; border: 1px solid #e1e4e8; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <header style="border-bottom: 3px solid #0071bc; padding-bottom: 15px; margin-bottom: 25px;">
                <h2 style="color: #0071bc; margin: 0;">📩 Spine Radiology Daily Report</h2>
                <p style="font-size: 0.8em; color: #999; margin-top: 15px;">  </p>
                <p style="font-size: 1.0em; color: #111111; margin-top: 15px;"> <a href="{info['pubmed_url']}" > {info['title']} </a> </p>
                <p style="font-size: 0.8em; color: #222222; margin-top: 15px;"> {info['journal']} | {info['date']} </p>
                <p style="font-size: 0.8em; color: #999; margin-top: 15px;">  </p>
            </header>
            
            <section style="margin-bottom: 25px;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 5px solid #0071bc;">
                    <div style="line-height: 1.8;">
                        {formatted_content}
                    </div>
                </div>
            </section>
            
            <footer style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                <a href="{info['pubmed_url']}" style="display: inline-block; background-color: #0071bc; color: white; padding: 12px 25px; text-decoration: none; border-radius: 6px; font-weight: bold;">PubMed 원문 보기</a>
                <p style="font-size: 0.8em; color: #999; margin-top: 15px;">본 메일은 PubMed 최신 논문을 분석하여 자동 발송되었습니다.</p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['Subject'] = f"[Daily Report] {info['title'][:60]}..."
#   msg['From'] = GMAIL_USER
    display_name = "추영 KSSR"
    msg['From'] = f"{Header(display_name, 'utf-8').encode()} <{GMAIL_USER}>"
    
    msg['To'] = receiver
    msg.attach(MIMEText(html_content, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PW)
        server.send_message(msg)


def send_telegram_message(info, content):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    # 텔레그램은 MarkdownV2보다 HTML 파싱이 안정적일 때가 많습니다.
    text = f"<b>[Daily Spine Radiology]</b>\n\n"
    text += f"<b>{info['title']}</b>\n\n"
    text += f"<i>{info['journal']} | {info['date']}</i>\n\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"{content}\n"
    text += f"━━━━━━━━━━━━━━━\n\n"
    text += f"🔗 <a href='{info['pubmed_url']}'>PubMed 보기</a>"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    
    res = requests.post(url, json=payload)
    return res.status_code



if __name__ == "__main__":
    info = get_latest_paper_details()
    if info:
        # [중요] summarize_and_translate에 'info' 딕셔너리를 전달
        content = summarize_and_translate(info)
        
        # 이메일 발송
        for email in RECEIVER_EMAILS:
            try:
                send_mail(info, content, email)
                print(f"Email success: {email}")
            except Exception as e:
                print(f"Email failed: {e}")
        
        # 텔레그램 발송
        print("Attempting to send Telegram message...")
        try:
#            status = send_telegram_message(info, content)
            if status == 200:
                print("Telegram success!")
        except Exception as e:
            print(f"Telegram failed: {e}")
    else:
        print("No papers found.")
