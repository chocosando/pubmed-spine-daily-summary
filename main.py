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
RECEIVER_EMAILS = [GMAIL_USER, "chocosando@daum.net", "agn70@yuhs.ac", "reanhea55@yuhs.ac", "classic0610@yuhs.ac", "andrew0668@yuhs.ac", "sando@yuhs.ac"] 

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
    # [수정] 영어 요약과 한글 번역을 동시에 요청하는 프롬프트
    prompt = f"""
    Summarize the following medical abstract into 3 bullet points in English (Objective, Findings, Clinical Implication).
    Then, provide a natural Korean translation for those 3 points.
    
    Abstract: {abstract}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional spine and musculoskeletal radiologist and medical translator."},
            {"role": "user", "content": prompt}
        ]
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
    msg['Subject'] = f"[추영][PubMed] {info['title'][:50]}..."
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
