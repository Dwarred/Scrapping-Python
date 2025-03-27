import random
import time
import requests
from fake_useragent import UserAgent
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import os

class ProxyManager:
    def __init__(self, proxies=None, rotation_interval=5):
        self.proxies = proxies or []
        self.current_proxy = None
        self.rotation_interval = rotation_interval
        self.last_rotation = 0
        self.ua = UserAgent()
        
    def add_proxy(self, proxy):
        """Ajoute un proxy au pool"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
            
    def add_proxies_from_file(self, filepath):
        """Charge des proxies depuis un fichier"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    proxy = line.strip()
                    if proxy and not proxy.startswith('#'):
                        self.add_proxy(proxy)
            return True
        except Exception as e:
            print(f"Erreur lors du chargement des proxies: {str(e)}")
            return False
            
    def add_proxies_from_encrypted_file(self, filepath, key):
        """Charge des proxies depuis un fichier chiffré"""
        try:
            if not os.path.exists(filepath):
                return False
                
            # Lire le contenu chiffré
            with open(filepath, 'rb') as f:
                encrypted_data = f.read()
                
            # Déchiffrer
            cipher = AES.new(key, AES.MODE_CBC, key[:16])
            decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
            
            # Traiter le contenu déchiffré
            proxies_text = decrypted_data.decode('utf-8')
            for line in proxies_text.split('\n'):
                proxy = line.strip()
                if proxy and not proxy.startswith('#'):
                    self.add_proxy(proxy)
            return True
        except Exception as e:
            print(f"Erreur lors du déchiffrement des proxies: {str(e)}")
            return False
    
    def save_proxies_to_encrypted_file(self, filepath, key):
        """Sauvegarde les proxies dans un fichier chiffré"""
        try:
            # Préparer les données
            proxies_text = '\n'.join(self.proxies)
            
            # Chiffrer
            cipher = AES.new(key, AES.MODE_CBC, key[:16])
            encrypted_data = cipher.encrypt(pad(proxies_text.encode('utf-8'), AES.block_size))
            
            # Écrire dans le fichier
            with open(filepath, 'wb') as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            print(f"Erreur lors du chiffrement des proxies: {str(e)}")
            return False
            
    def get_proxy(self, force_rotation=False):
        """Obtient un proxy, avec rotation si nécessaire"""
        if not self.proxies:
            return None
            
        current_time = time.time()
        
        # Rotation basée sur le temps ou forcée
        if force_rotation or not self.current_proxy or (current_time - self.last_rotation > self.rotation_interval):
            self.current_proxy = random.choice(self.proxies)
            self.last_rotation = current_time
            
        return self.current_proxy
        
    def get_session_with_proxy(self):
        """Crée une session requests avec un proxy configuré"""
        session = requests.Session()
        
        proxy = self.get_proxy()
        if proxy:
            session.proxies = {
                'http': proxy,
                'https': proxy
            }
            
        # Configurer un user agent aléatoire
        session.headers.update({'User-Agent': self.ua.random})
        
        return session
    
    def test_proxy(self, proxy, test_url="https://www.google.com", timeout=5):
        """Teste si un proxy fonctionne"""
        try:
            session = requests.Session()
            session.proxies = {
                'http': proxy,
                'https': proxy
            }
            session.headers.update({'User-Agent': self.ua.random})
            
            response = session.get(test_url, timeout=timeout)
            return response.status_code == 200
        except:
            return False
    
    def test_all_proxies(self, test_url="https://www.google.com", timeout=5):
        """Teste tous les proxies et élimine ceux qui ne fonctionnent pas"""
        working_proxies = []
        for proxy in self.proxies:
            if self.test_proxy(proxy, test_url, timeout):
                working_proxies.append(proxy)
        
        # Mettre à jour la liste
        self.proxies = working_proxies
        return len(working_proxies)