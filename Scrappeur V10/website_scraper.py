import re
import time
import random
import requests
from bs4 import BeautifulSoup
import validators
import tldextract
from fake_useragent import UserAgent

class WebsiteScraper:
    def __init__(self, session=None, timeout=10, delay_range=(1, 3)):
        self.session = session if session else requests.Session()
        self.ua = UserAgent()
        self.timeout = timeout
        self.delay_range = delay_range
        
    def get_random_delay(self):
        return random.uniform(self.delay_range[0], self.delay_range[1])
    
    def get_headers(self):
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def is_valid_url(self, url):
        return validators.url(url) if url and url != "N/A" else False
    
    def visit_website(self, url, log_callback=None):
        """Visite un site web et extrait les emails et autres informations"""
        if not self.is_valid_url(url):
            if log_callback:
                log_callback(f"URL invalide: {url}")
            return None
            
        # Ajouter un délai aléatoire
        time.sleep(self.get_random_delay())
        
        try:
            if log_callback:
                log_callback(f"Visite du site web: {url}")
                
            response = self.session.get(url, headers=self.get_headers(), timeout=self.timeout)
            response.raise_for_status()
            
            # Extraire le domaine pour le logging
            domain = tldextract.extract(url).registered_domain
            
            if log_callback:
                log_callback(f"Page téléchargée: {domain} ({len(response.text)} caractères)")
                
            return response.text
            
        except Exception as e:
            if log_callback:
                log_callback(f"Erreur lors de la visite de {url}: {str(e)}")
            return None
    
    def extract_emails_from_website(self, html_content, existing_emails=None, log_callback=None):
        """Extrait tous les emails d'une page web"""
        if not html_content:
            return []
            
        existing_emails = existing_emails or []
        found_emails = []
        
        # Extraction par regex
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_matches = re.findall(email_pattern, html_content)
        
        # Filtrage des emails
        for email in email_matches:
            # Ignorer les emails déjà trouvés
            if email in existing_emails or email in found_emails:
                continue
                
            # Ignorer les domaines d'exemple
            if any(fake in email.lower() for fake in ['example.com', 'yourdomain', 'domain.com']):
                continue
                
            # Vérifier le format de l'email
            if validators.email(email):
                found_emails.append(email)
                if log_callback:
                    log_callback(f"Email trouvé sur site web: {email}")
        
        # Extraction par BeautifulSoup (liens mailto:)
        soup = BeautifulSoup(html_content, 'html.parser')
        mailto_links = soup.find_all('a', href=lambda href: href and 'mailto:' in href)
        
        for link in mailto_links:
            href = link.get('href', '')
            if 'mailto:' in href:
                email = href.replace('mailto:', '').strip().split('?')[0]  # Supprimer les paramètres
                
                if email and '@' in email and validators.email(email):
                    if email not in existing_emails and email not in found_emails:
                        found_emails.append(email)
                        if log_callback:
                            log_callback(f"Email trouvé (mailto): {email}")
        
        # Recherche de formulaires de contact
        contact_forms = soup.find_all(['form', 'div', 'section'], 
                               class_=lambda x: x and ('contact' in x.lower() or 'kontakt' in x.lower()))
        
        if contact_forms and log_callback:
            log_callback(f"Formulaire de contact détecté ({len(contact_forms)} trouvés)")
        
        return found_emails
        
    def extract_phone_numbers(self, html_content, log_callback=None):
        """Extrait les numéros de téléphone d'une page web avec formats variés"""
        if not html_content:
            return []
            
        # Motifs de téléphone suisses
        phone_patterns = [
            r'(\+41\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2})',  # +41 xx xxx xx xx
            r'(0\d{2}\s*\d{3}\s*\d{2}\s*\d{2})',        # 0xx xxx xx xx
            r'(\d{3}\s*\d{2}\s*\d{2}\s*\d{2})'          # xxx xx xx xx
        ]
        
        phones = []
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                # Normaliser le format
                clean_phone = re.sub(r'\s+', '', match)
                if clean_phone not in phones:
                    phones.append(clean_phone)
                    if log_callback:
                        log_callback(f"Téléphone trouvé: {clean_phone}")
        
        # Recherche par BeautifulSoup (liens tel:)
        soup = BeautifulSoup(html_content, 'html.parser')
        tel_links = soup.find_all('a', href=lambda href: href and 'tel:' in href)
        
        for link in tel_links:
            href = link.get('href', '')
            if 'tel:' in href:
                phone = href.replace('tel:', '').strip()
                clean_phone = re.sub(r'[\s-]', '', phone)
                
                if clean_phone and clean_phone not in phones:
                    phones.append(clean_phone)
                    if log_callback:
                        log_callback(f"Téléphone trouvé (tel:): {clean_phone}")
        
        return phones
    
    def extract_social_media(self, html_content, log_callback=None):
        """Extrait les liens vers les réseaux sociaux"""
        if not html_content:
            return {}
            
        soup = BeautifulSoup(html_content, 'html.parser')
        social_media = {}
        
        # Plateformes sociales à rechercher
        platforms = {
            'facebook': r'facebook\.com',
            'linkedin': r'linkedin\.com',
            'twitter': r'twitter\.com|x\.com',
            'instagram': r'instagram\.com',
            'youtube': r'youtube\.com',
        }
        
        for platform, pattern in platforms.items():
            for link in soup.find_all('a', href=re.compile(pattern)):
                url = link.get('href', '')
                if url and url not in social_media.get(platform, []):
                    if platform not in social_media:
                        social_media[platform] = []
                    social_media[platform].append(url)
                    if log_callback:
                        log_callback(f"Lien {platform} trouvé: {url}")
        
        return social_media
