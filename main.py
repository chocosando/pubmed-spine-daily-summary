import os
from Bio import Entrez
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 환경 변수 및 설정
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PW = os.getenv('GMAIL_PASSWORD')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')

# [수정] 받는 사람 이메일 주소들을 리스트로 관리하세요.
RECEIVER_EMAILS = [GMAIL_USER, "chocosando@daum.net", "agn70@yuhs.ac", "reanhea55@yuhs.ac", "classic0610@yuhs.ac", "andrew0668@yuhs.ac", "sando@yuhs.ac", "jaywony@gmail.com", "jjdragon112@gmail.com"] 

def get_latest_paper_details():
    Entrez.email = GMAIL_USER

    # MSK Radiology 관련 최신 논문 검색 (테스트를 위해 기간 30일 설정)
    #query = '("Spine"[Mesh] OR "Radiology"[Journal]) AND "last 60 days"[dp]'
    #handle = Entrez.esearch(db="pubmed", term=query, sort="relevance", retmax=1)
    #record = Entrez.read(handle)
    #id_list = record["IdList"]
    
    # [개선] 1. 영향력 있는 저널 리스트 지정
    top_journals = '("Radiology"[Journal] OR "Lancet"[Journal] OR "New England Journal of Medicine"[Journal] OR "Nature Medicine"[Journal] OR "JAMA"[Journal])'
    
    # [개선] 2. 관심 키워드와 결합 (MSK 및 AI 관련 예시)
    # retmax를 5정도로 늘려 후보군을 뽑은 뒤 그 중 첫 번째를 선택하면 더 정확합니다.
    query = f'{top_journals} AND ("Musculoskeletal"[Mesh] OR "Artificial Intelligence"[Mesh]) AND "last 30 days"[dp]'
    
    # [개선] 3. sort="relevance" (관련도순) 혹은 "pub_date" (최신순) 설정
    handle = Entrez.esearch(db="pubmed", term=query, sort="relevance", retmax=1)
    record = Entrez.read(handle)
    id_list = record["IdList"]
    
    if not id_list:
        # 만약 너무 좁은 쿼리로 결과가 없다면, 좀 더 넓은 쿼리로 재검색하는 로직
        query_fallback = '("Spine"[Mesh] OR "Radiology"[Journal]) AND "last 60 days"[dp]'
        handle = Entrez.esearch(db="pubmed", term=query_fallback, sort="relevance", retmax=1)
        record = Entrez.read(handle)
        id_list = record["IdList"]

    if not id_list:
        return None
    
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
    
    return {
        "title": title, "abstract": abstract, "authors": author_text,
        "journal": journal, "pmid": pmid, "doi": doi,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": f"https://doi.org/{doi}" if doi != "N/A" else "#"
    }

def summarize_and_translate(abstract):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    
    # [개선] 분량을 2배로 늘리고 상세 지표를 포함하는 심층 프롬프트
    prompt = f"""
    You are an expert Musculoskeletal Radiologist and Medical Scientist (M.D.-Ph.D.). 
    Analyze the provided abstract in great detail for a specialist-level report.

    [Guidelines]
    1. Expand the content to be twice as detailed as a standard summary.
    2. Write in Korean, but ALWAYS include key technical and medical terms in English brackets [English Term].
    3. Ensure the summary covers:
       - 서론 및 연구 목적 [Introduction & Objective]: 연구의 배경과 가설을 상세히 기술.
       - 대상 및 방법론 [Materials & Methods]: 환자 군[Cohort], 모델 구조[Architecture], 학습 방법[Training] 등 포함.
       - 결과 분석 및 통계 [Results & Statistical Analysis]: 구체적인 수치[Numerical values], 신뢰구간[CI], 유의수준[p-value]을 반드시 포함.
       - 고찰 및 임상적 가치 [Discussion & Clinical Value]: 실제 판독 현장에서의 의의와 기대 효과.
       - 연구의 한계점 [Limitations]: 초록에서 언급된 제약 사항 기술.

    Abstract: {abstract}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o", # 정보량이 많아지므로 논리력이 필요하다면 "gpt-4o"를 강력 추천합니다.
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

if __name__ == "__main__":
    info = get_latest_paper_details()
    if info:
        content = summarize_and_translate(info['abstract'])
        # [수정] 여러 명에게 발송
        for email in RECEIVER_EMAILS:
            try:
                send_mail(info, content, email)
                print(f"Success: Sent to {email}")
            except Exception as e:
                print(f"Failed: {email} - {e}")
    else:
        print("No papers found.")
