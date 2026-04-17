import os
import requests
from Bio import Entrez
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

# 환경 변수 및 설정
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PW = os.getenv('GMAIL_PASSWORD')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RECEIVER_EMAILS = [GMAIL_USER] 

def get_latest_paper_details():
    Entrez.email = GMAIL_USER
    
    journal_list = [
        "Radiology", "Radiology. Artificial intelligence", "Lancet Digital Health",
        "European Radiology", "Skeletal radiology", "AJR. American journal of roentgenology",
        "Korean Journal of radiology", "European journal of Radiology", "Scientific Reports",
        "Nature Medicine", "Nature Communications", "Lancet", "Spine", "The Spine Journal",
        "AJNR. American journal of neuroradiology", "Neuroradiology", "Bone & joint journal",
        "PLoS ONE", "JAMA"
    ]

    journals = " OR ".join([f'"{j}"[Journal]' for j in journal_list])
    topics = '("Spine"[Mesh] OR "Spinal Cord"[Mesh] OR "Spondylosis"[Mesh] OR "Intervertebral Disc"[Mesh] OR "Spinal Diseases"[Mesh] OR "Vertebrae"[Title/Abstract])'

    # 최신성 확보를 위한 쿼리
    query = f"({journals}) AND {topics} AND hasabstract[Filter] AND (2024:2030[pdat])"
    
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
    Analyze the provided abstract in great detail for
