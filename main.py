import os
from Bio import Entrez
import openai
import smtplib
from email.mime.text import MIMEText

# 1. 환경 설정 (비밀 정보는 나중에 GitHub에서 관리)
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PW = os.getenv('GMAIL_PASSWORD')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
RECEIVER_EMAIL = GMAIL_USER  # 본인에게 보낼 경우

# 2. PubMed에서 인기 논문 찾기
def get_latest_paper():
    Entrez.email = GMAIL_USER
    # 검색어: 최근 7일간 MSK Radiology 관련 가장 관련도 높은 논문 1개
    query = '("Radiology"[Mesh] OR "Spine"[Mesh])' # AND "last 30 days"[dp]'
    handle = Entrez.esearch(db="pubmed", term=query, sort="relevance", retmax=1)
    record = Entrez.read(handle)
    id_list = record["IdList"]
    
    if not id_list: return None
    
    fetch_handle = Entrez.efetch(db="pubmed", id=id_list[0], rettype="abstract", retmode="text")
    return fetch_handle.read()

# 3. OpenAI를 이용한 영어 요약
def summarize_paper(abstract):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
#        model="gpt-4o", # 또는 gpt-3.5-turbo
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a medical researcher. Summarize the abstract in English with 3 clear bullet points: Objective, Key Findings, and Clinical Implication."},
            {"role": "user", "content": abstract}
        ]
    )
    return response.choices[0].message.content
 
# 4. 이메일 전송
def send_mail(content):
    msg = MIMEText(content)
    msg['Subject'] = "Today's PubMed MSK Summary"
    msg['From'] = GMAIL_USER
    msg['To'] = RECEIVER_EMAIL

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PW)
        server.send_message(msg)

# 실행 프로세스
#if __name__ == "__main__":
#    paper_abstract = get_latest_paper()
#    if paper_abstract:
#        summary = summarize_paper(paper_abstract)
#        send_mail(summary)
#        print("Success!")
        
if __name__ == "__main__":
    print("Step 1: Searching PubMed...")
    paper_abstract = get_latest_paper()
    
    if paper_abstract:
        print("Step 2: Paper found! Summarizing...")
        summary = summarize_paper(paper_abstract)
        
        print("Step 3: Sending Email...")
        send_mail(summary)
        
        print("Success!")
    else:
        print("No papers found with the current query.") # 결과가 없을 때 출력됨
