import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import time
import pandas as pd
from datetime import datetime
import threading
import re
import random
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import validators
import os
from proxy_manager import ProxyManager
from website_scraper import WebsiteScraper

class LocalChScraper:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Local.ch Scraper")
        self.root.geometry("800x700")
        
        # Variables
        self.keywords = tk.StringVar()
        self.num_pages = tk.StringVar(value="1")
        self.current_task = tk.StringVar(value="En attente...")
        self.total_emails = 0
        self.progress_bars = {}  # Stockage des barres de progression pour chaque mot-clé
        self.email_counters = {}  # Compteurs d'emails pour chaque mot-clé
        self.time_counters = {}   # Compteurs de temps pour chaque mot-clé
        self.location = tk.StringVar(value="Genève")  # Localisation par défaut
        self.search_radius = tk.IntVar(value=0)  # Rayon de recherche en km (0 = pas de limite)
        
        # Options avancées
        self.visit_websites = tk.BooleanVar(value=True)  # Visiter les sites web par défaut
        self.max_website_pages = tk.IntVar(value=1)      # Nombre de pages à explorer par site
        self.use_proxies = tk.BooleanVar(value=False)    # Utiliser des proxies
        self.skip_found = tk.BooleanVar(value=True)      # Éviter de revisiter les entreprises déjà traitées
        
        # Gestion des erreurs et des pauses
        self.pause_flag = threading.Event()
        self.stop_flag = threading.Event()
        self.seen_emails = set()  # Pour éviter les doublons
        self.processed_urls = set()  # URLs déjà traitées
        
        # User agent pour imiter un navigateur différent à chaque requête
        self.ua = UserAgent()
        
        # Session HTTP réutilisable
        self.session = requests.Session()
        
        # Gestionnaire de proxies
        self.proxy_manager = ProxyManager()
        
        # Web scraper pour les sites d'entreprises
        self.website_scraper = WebsiteScraper(self.session)
        
        # Créer l'interface graphique d'abord
        self.create_gui()
        
        # Puis initialiser la base de données
        self.setup_database()
        
        # Charger les emails et URLs déjà traités
        self.load_existing_data()
        
    def create_gui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Entrées
        ttk.Label(main_frame, text="Mots-clés (séparés par des virgules):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.keywords, width=50).grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Label(main_frame, text="Nombre de pages:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.num_pages, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(main_frame, text="Localisation:").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.location, width=20).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Rayon de recherche
        radius_frame = ttk.Frame(main_frame)
        radius_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(radius_frame, text="Rayon de recherche:").grid(row=0, column=0, sticky=tk.W)
        
        # Afficher la valeur actuelle du rayon
        radius_value_var = tk.StringVar(value="0 km")
        
        def update_radius_label(*args):
            radius_value_var.set(f"{self.search_radius.get()} km")
        
        self.search_radius.trace_add("write", update_radius_label)
        
        # Slider pour le rayon
        radius_scale = ttk.Scale(radius_frame, from_=0, to=100, orient="horizontal", 
                               variable=self.search_radius, length=200)
        radius_scale.grid(row=0, column=1, padx=5)
        
        # Entrée manuelle pour le rayon
        radius_entry = ttk.Spinbox(radius_frame, from_=0, to=100, textvariable=self.search_radius, width=5)
        radius_entry.grid(row=0, column=2, padx=5)
        
        # Label pour afficher l'unité
        ttk.Label(radius_frame, textvariable=radius_value_var).grid(row=0, column=3, padx=(0, 10))
        
        # Options avancées
        options_frame = ttk.LabelFrame(main_frame, text="Options avancées")
        options_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Option pour visiter les sites web
        ttk.Checkbutton(options_frame, text="Visiter les sites web", variable=self.visit_websites).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(options_frame, text="Pages par site:").grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Spinbox(options_frame, from_=1, to=5, textvariable=self.max_website_pages, width=5).grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        
        # Option pour ignorer les entreprises déjà traitées
        ttk.Checkbutton(options_frame, text="Ignorer les entreprises déjà traitées", variable=self.skip_found).grid(row=0, column=3, sticky=tk.W, padx=20, pady=2)
        
        # Option pour utiliser des proxies
        proxy_frame = ttk.Frame(options_frame)
        proxy_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=5, pady=2)
        
        ttk.Checkbutton(proxy_frame, text="Utiliser des proxies", variable=self.use_proxies).grid(row=0, column=0, sticky=tk.W)
        ttk.Button(proxy_frame, text="Charger des proxies", command=self.load_proxies).grid(row=0, column=1, padx=5)
        self.proxy_count_label = ttk.Label(proxy_frame, text="0 proxies chargés")
        self.proxy_count_label.grid(row=0, column=2, padx=5)
        
        # Boutons dans un frame séparé
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        
        ttk.Button(button_frame, text="▶ Démarrer", command=self.start_scraping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="⏸ Pause", command=lambda: self.pause_flag.set()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="▶ Reprendre", command=lambda: self.pause_flag.clear()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🟥 Stop", command=lambda: self.stop_flag.set()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exporter en Excel", command=self.export_to_excel).pack(side=tk.RIGHT, padx=5)
        
        # Label pour le total d'emails
        self.total_emails_label = ttk.Label(main_frame, text="Total d'emails: 0")
        self.total_emails_label.grid(row=6, column=0, columnspan=1, pady=(10, 5), sticky=tk.W)
        
        # Timer label
        self.timer_label = ttk.Label(main_frame, text="⏱ Temps: 0s")
        self.timer_label.grid(row=6, column=1, pady=(10, 5), sticky=tk.E)
        
        # Frame pour les barres de progression
        self.progress_frame = ttk.LabelFrame(main_frame, text="Progression par mot-clé")
        self.progress_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10, padx=5)
        main_frame.rowconfigure(7, weight=1)
        
        # Scrollbar pour les barres de progression
        self.progress_canvas = tk.Canvas(self.progress_frame)
        self.scrollbar = ttk.Scrollbar(self.progress_frame, orient="vertical", command=self.progress_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.progress_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.progress_canvas.configure(
                scrollregion=self.progress_canvas.bbox("all")
            )
        )
        
        self.progress_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.progress_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.progress_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Log area
        self.log_frame = ttk.LabelFrame(main_frame, text="Logs")
        self.log_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10, padx=5)
        
        self.log_text = tk.Text(self.log_frame, height=10, width=80)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
    def load_proxies(self):
        """Charge une liste de proxies depuis un fichier"""
        file_path = filedialog.askopenfilename(
            title="Sélectionner un fichier de proxies",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        
        if not file_path:
            return
            
        if self.proxy_manager.add_proxies_from_file(file_path):
            # Mettre à jour le compteur
            count = len(self.proxy_manager.proxies)
            self.proxy_count_label.config(text=f"{count} proxies chargés")
            self.log(f"Chargé {count} proxies depuis {file_path}")
            
            # Tester les proxies
            self.root.after(100, self.test_proxies)
        else:
            messagebox.showerror("Erreur", f"Impossible de charger les proxies depuis {file_path}")
    
    def test_proxies(self):
        """Teste les proxies chargés pour vérifier qu'ils fonctionnent"""
        def run_test():
            self.log("Test des proxies en cours...")
            working = self.proxy_manager.test_all_proxies()
            self.proxy_count_label.config(text=f"{working} proxies fonctionnels")
            self.log(f"Test terminé: {working} proxies fonctionnels sur {len(self.proxy_manager.proxies)}")
        
        # Lancer dans un thread séparé
        thread = threading.Thread(target=run_test)
        thread.daemon = True
        thread.start()
        
    def setup_database(self):
        with sqlite3.connect('localch_data.db') as conn:
            cursor = conn.cursor()
            
            # Créer la table si elle n'existe pas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT,
                    name TEXT,
                    address TEXT,
                    phone TEXT,
                    email TEXT,
                    website TEXT,
                    date_added TIMESTAMP,
                    url TEXT
                )
            ''')
            
            # Vérifier si la colonne website existe, sinon l'ajouter
            try:
                cursor.execute("SELECT website FROM contacts LIMIT 1")
                print("La colonne 'website' existe déjà")
            except sqlite3.OperationalError:
                print("Ajout de la colonne 'website' à la base de données existante")
                cursor.execute("ALTER TABLE contacts ADD COLUMN website TEXT")
                conn.commit()
                self.log("Colonne 'website' ajoutée à la base de données")
            
            # Vérifier si la colonne url existe, sinon l'ajouter
            try:
                cursor.execute("SELECT url FROM contacts LIMIT 1")
                print("La colonne 'url' existe déjà")
            except sqlite3.OperationalError:
                print("Ajout de la colonne 'url' à la base de données existante")
                cursor.execute("ALTER TABLE contacts ADD COLUMN url TEXT")
                conn.commit()
                self.log("Colonne 'url' ajoutée à la base de données")
            
            # Créer un index sur l'email pour accélérer les recherches
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_email ON contacts(email)
            ''')
            
            # Créer un index sur l'url pour accélérer les recherches
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_url ON contacts(url)
            ''')
    
    def load_existing_data(self):
        """Charge les emails et URLs déjà présents dans la base de données"""
        try:
            with sqlite3.connect('localch_data.db') as conn:
                cursor = conn.cursor()
                
                # Charger les emails existants
                cursor.execute("SELECT DISTINCT email FROM contacts WHERE email IS NOT NULL AND email != ''")
                emails = cursor.fetchall()
                for email in emails:
                    if email[0]:  # S'assurer que l'email n'est pas None ou vide
                        self.seen_emails.add(email[0])
                
                # Charger les URLs déjà traitées
                cursor.execute("SELECT DISTINCT url FROM contacts WHERE url IS NOT NULL AND url != ''")
                urls = cursor.fetchall()
                for url in urls:
                    if url[0]:  # S'assurer que l'URL n'est pas None ou vide
                        self.processed_urls.add(url[0])
                
                self.log(f"Chargé {len(self.seen_emails)} emails et {len(self.processed_urls)} URLs déjà traités")
        except Exception as e:
            self.log(f"Erreur lors du chargement des données existantes: {str(e)}")
    
    def start_scraping(self):
        """Démarre le processus de scraping"""
        keywords = [k.strip() for k in self.keywords.get().split(',') if k.strip()]
        if not keywords:
            messagebox.showerror("Erreur", "Veuillez entrer au moins un mot-clé")
            return
            
        try:
            num_pages = int(self.num_pages.get())
            if num_pages < 1:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Erreur", "Le nombre de pages doit être un nombre entier positif")
            return
        
        # Réinitialiser les flags et compteurs
        self.pause_flag.clear()
        self.stop_flag.clear()
        self.seen_emails.clear()
        self.total_emails = 0
        self.total_emails_label.config(text="Total d'emails: 0")
        
        # Nettoyer les logs
        self.log_text.delete(1.0, tk.END)
        
        # Nettoyer les anciennes barres de progression
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.progress_bars = {}
        self.email_counters = {}
        self.time_counters = {}
        
        # Créer les barres de progression pour chaque mot-clé
        for i, keyword in enumerate(keywords):
            self.create_progress_bar_for_keyword(keyword, i)
        
        # Démarrer le timer
        self.start_timer()
        
        # Initialiser une nouvelle session avec ou sans proxy
        if self.use_proxies.get() and self.proxy_manager.proxies:
            self.log(f"Utilisation de {len(self.proxy_manager.proxies)} proxies")
            self.session = self.proxy_manager.get_session_with_proxy()
        else:
            self.session = requests.Session()
            
        # Lancer le scraping dans un thread séparé
        thread = threading.Thread(target=self.scrape_keywords, args=(keywords, num_pages))
        thread.daemon = True
        thread.start()
        
    def scrape_keywords(self, keywords, num_pages):
        """Fonction principale de scraping utilisant requests"""
        try:
            for keyword in keywords:
                if self.stop_flag.is_set():
                    break
                
                self.log(f"(recherche) Scraping pour: {keyword}")
                emails_found = 0
                start_time = time.time()
                
                location = self.location.get()
                radius = self.search_radius.get()
                
                for page_num in range(1, num_pages + 1):
                    if self.stop_flag.is_set():
                        break
                    
                    # Attendre si en pause
                    while self.pause_flag.is_set() and not self.stop_flag.is_set():
                        time.sleep(0.5)
                    
                    # URL de la page de résultats avec localisation personnalisée et rayon
                    radius_param = f"&distance={radius}" if radius > 0 else ""
                    search_url = f"https://www.local.ch/fr/q?what={keyword}&where={location}{radius_param}&page={page_num}"
                    
                    # Faire la requête avec un délai aléatoire et des en-têtes aléatoires
                    time.sleep(self.get_random_delay())
                    try:
                        location_display = f"{location}" if radius == 0 else f"{location} (rayon: {radius} km)"
                        self.log(f"Accès à la page {page_num} pour '{keyword}' à {location_display}")
                        response = self.session.get(search_url, headers=self.get_headers(), timeout=10)
                        response.raise_for_status()
                    except Exception as e:
                        self.log(f"(attention) Erreur lors de l'accès à {search_url}: {str(e)}")
                        
                        # Si on utilise des proxies, essayer d'en changer
                        if self.use_proxies.get() and self.proxy_manager.proxies:
                            self.log("Changement de proxy...")
                            self.session = self.proxy_manager.get_session_with_proxy(force_rotation=True)
                            continue
                        else:
                            continue
                    
                    # Extraire les liens des entreprises
                    company_links = self.extract_data_from_search_page(response.text, keyword)
                    
                    # Si aucun lien n'est trouvé, passer à la page suivante
                    if not company_links:
                        self.log(f"Aucune entreprise trouvée sur la page {page_num} pour '{keyword}'")
                        continue
                    
                    # Traiter chaque entreprise
                    for link_index, company_link in enumerate(company_links):
                        if self.stop_flag.is_set():
                            break
                        
                        # Attendre si en pause
                        while self.pause_flag.is_set() and not self.stop_flag.is_set():
                            time.sleep(0.5)
                        
                        # Construire l'URL complète
                        detail_url = f"https://www.local.ch{company_link}" if company_link.startswith('/') else company_link
                        
                        # Vérifier si l'URL a déjà été traitée
                        if self.skip_found.get() and detail_url in self.processed_urls:
                            self.log(f"URL déjà traitée, ignorée: {detail_url}")
                            continue
                        
                        # Faire la requête avec un délai aléatoire et des en-têtes aléatoires
                        time.sleep(self.get_random_delay())
                        try:
                            self.log(f"Analyse de l'entreprise {link_index+1}/{len(company_links)}: {detail_url}")
                            company_response = self.session.get(detail_url, headers=self.get_headers(), timeout=10)
                            company_response.raise_for_status()
                        except Exception as e:
                            self.log(f"(attention) Erreur lors de l'accès à {detail_url}: {str(e)}")
                            
                            # Si on utilise des proxies, essayer d'en changer
                            if self.use_proxies.get() and self.proxy_manager.proxies:
                                self.log("Changement de proxy...")
                                self.session = self.proxy_manager.get_session_with_proxy(force_rotation=True)
                            continue
                        
                        # Extraire les données de l'entreprise
                        company_data = self.extract_company_data(company_response.text, detail_url)
                        
                        # Visiter le site web de l'entreprise si activé et disponible
                        if self.visit_websites.get() and company_data['website'] != "N/A" and validators.url(company_data['website']):
                            self.log(f"Visite du site web de l'entreprise: {company_data['website']}")
                            try:
                                # Utiliser le website_scraper pour extraire plus de données
                                html_content = self.website_scraper.visit_website(
                                    company_data['website'], 
                                    log_callback=self.log
                                )
                                
                                if html_content:
                                    # Extraire des emails supplémentaires du site web
                                    website_emails = self.website_scraper.extract_emails_from_website(
                                        html_content, 
                                        existing_emails=company_data['emails'],
                                        log_callback=self.log
                                    )
                                    
                                    # Ajouter les emails trouvés
                                    for email in website_emails:
                                        if email not in company_data['emails']:
                                            company_data['emails'].append(email)
                                    
                                    # Extraire des numéros de téléphone supplémentaires
                                    website_phones = self.website_scraper.extract_phone_numbers(
                                        html_content,
                                        log_callback=self.log
                                    )
                                    
                                    if website_phones and company_data['phone'] == "N/A":
                                        company_data['phone'] = website_phones[0]
                            except Exception as e:
                                self.log(f"Erreur lors de la visite du site web: {str(e)}")
                        
                        # Traiter les emails trouvés
                        for email in company_data['emails']:
                            if email not in self.seen_emails:
                                self.seen_emails.add(email)
                                
                                # Sauvegarder dans la base de données
                                with sqlite3.connect('localch_data.db') as conn:
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        INSERT INTO contacts (keyword, name, address, phone, email, website, date_added, url)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (
                                        keyword,
                                        company_data['name'],
                                        company_data['address'],
                                        company_data['phone'],
                                        email,
                                        company_data['website'],
                                        datetime.now(),
                                        company_data['url']
                                    ))
                                
                                # Ajouter l'URL aux URLs déjà traitées
                                self.processed_urls.add(company_data['url'])
                                
                                # Mettre à jour les compteurs
                                emails_found += 1
                                self.total_emails += 1
                                
                                # Mettre à jour l'interface - utiliser une fonction pour éviter les problèmes de capture de variables
                                def update_ui():
                                    self.total_emails_label.config(text=f"Total d'emails: {self.total_emails}")
                                    self.email_counters[keyword].config(text=f"Emails: {emails_found}")
                                    # Mettre à jour aussi la barre de progression pour montrer une progression continue
                                    progress_value = (page_num / num_pages) * 100
                                    self.progress_bars[keyword]["bar"].config(value=progress_value)
                                    self.progress_bars[keyword]["status"].config(text=f"Progression: {progress_value:.1f}%")
                                
                                self.root.after(0, update_ui)
                                
                                # Log
                                self.log(f"(email) Trouvé: {company_data['name']} - {email}")
                    
                    # Mettre à jour la barre de progression
                    progress = (page_num / num_pages) * 100
                    elapsed_time = time.time() - start_time
                    
                    # Mettre à jour l'interface utilisateur de façon fiable avec une fonction
                    def update_progress_ui():
                        self.progress_bars[keyword]["bar"].config(value=progress)
                        self.email_counters[keyword].config(text=f"Emails: {emails_found}")
                        self.time_counters[keyword].config(text=f"Temps: {elapsed_time:.1f}s")
                        self.progress_bars[keyword]["status"].config(text=f"Progression: {progress:.1f}%")
                    
                    self.root.after(0, update_progress_ui)
                
                # Marquer la tâche comme terminée
                self.root.after(0, lambda k=keyword, e=emails_found: (
                    self.progress_bars[k]["bar"].config(value=100),
                    self.progress_bars[k]["status"].config(text=f"(ok) Terminé! {e} emails trouvés", foreground="green"),
                    self.progress_bars[k]["frame"].config(background="#e6ffe6")  # Fond vert pâle
                ))
                
                self.log(f"(ok) Terminé pour '{keyword}' - {emails_found} emails trouvés")
            
            # Toutes les tâches sont terminées
            if not self.stop_flag.is_set():
                self.current_task.set(f"(ok) Terminé! Total: {self.total_emails} emails trouvés")
                
                # Afficher une popup de fin de tâche
                self.root.after(0, lambda: messagebox.showinfo("Scraping terminé", 
                    f"(ok) Toutes les tâches sont terminées!\n\n"
                    f"- Total d'emails trouvés: {self.total_emails}\n"
                    f"- Mots-clés traités: {len(keywords)}\n"
                    f"- Nombre de pages par mot-clé: {num_pages}"
                ))
        
        except Exception as e:
            self.log(f"(erreur) Erreur générale: {str(e)}")
            
    def get_random_delay(self):
        """Retourne un délai aléatoire entre 1 et 3 secondes"""
        return random.uniform(1, 3)
    
    def get_headers(self):
        """Retourne des en-têtes HTTP aléatoires pour imiter un navigateur"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def extract_data_from_search_page(self, html_content, keyword):
        """Extraire les liens des entreprises depuis la page de résultats"""
        soup = BeautifulSoup(html_content, 'html.parser')
        company_links = []
        
        # Chercher tous les liens qui correspondent aux résultats de recherche
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            # Liens vers des pages de détail d'entreprise
            if '/fr/d/' in href and href not in company_links:
                company_links.append(href)
        
        self.log(f"Trouvé {len(company_links)} entreprises pour '{keyword}'")
        return company_links
    
    def extract_company_data(self, html_content, url):
        """Extraire les informations d'une entreprise à partir de sa page de détail"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extraire le nom
        name = "N/A"
        name_tag = soup.find('h1')
        if name_tag:
            name = name_tag.text.strip()
        
        # Extraire l'adresse
        address = "N/A"
        address_tag = soup.find('address')
        if address_tag:
            address = address_tag.get_text(strip=True).replace('\n', ', ')
        
        # Extraire le téléphone
        phone = "N/A"
        phone_match = re.search(r'tel:([+\d\s]+)', html_content)
        if phone_match:
            phone = phone_match.group(1).strip()
        
        # Extraire le site web
        website = "N/A"
        website_links = soup.find_all('a', href=True)
        for link in website_links:
            href = link.get('href', '')
            if 'http' in href and 'local.ch' not in href and 'mailto:' not in href and 'tel:' not in href:
                website = href
                break
        
        # Extraire les emails avec regex
        emails = []
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_matches = re.findall(email_pattern, html_content)
        
        # Filtrer les emails pour éviter les domaines d'exemple
        valid_emails = [email for email in email_matches if not any(fake in email.lower() for fake in ['example.com', 'yourdomain', 'domain.com'])]
        
        # Améliorer la recherche d'emails - chercher dans les attributs href contenant mailto:
        mailto_links = soup.find_all('a', href=lambda href: href and 'mailto:' in href)
        for link in mailto_links:
            href = link.get('href', '')
            if 'mailto:' in href:
                email = href.replace('mailto:', '').strip()
                if email and '@' in email and email not in valid_emails:
                    valid_emails.append(email)
        
        if valid_emails:
            emails = valid_emails
        
        return {
            'name': name,
            'address': address,
            'phone': phone,
            'website': website,
            'emails': emails,
            'url': url
        }
    
    def create_progress_bar_for_keyword(self, keyword, row):
        # Frame pour contenir les informations de progression d'un mot-clé
        keyword_frame = ttk.Frame(self.scrollable_frame)
        keyword_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Label du mot-clé
        keyword_label = ttk.Label(keyword_frame, text=f"{keyword}:")
        keyword_label.grid(row=0, column=0, sticky=tk.W)
        
        # Barre de progression
        progress_bar = ttk.Progressbar(keyword_frame, length=300, mode="determinate")
        progress_bar.grid(row=0, column=1, padx=(5, 10))
        
        # Labels pour afficher les compteurs
        email_counter = ttk.Label(keyword_frame, text="Emails: 0")
        email_counter.grid(row=0, column=2, padx=5)
        
        time_counter = ttk.Label(keyword_frame, text="Temps: 0s")
        time_counter.grid(row=0, column=3, padx=5)
        
        # Label pour le statut
        status_label = ttk.Label(keyword_frame, text="En attente...", foreground="blue")
        status_label.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(2, 0))
        
        # Stocker les références
        self.progress_bars[keyword] = {
            "bar": progress_bar,
            "status": status_label,
            "frame": keyword_frame
        }
        self.email_counters[keyword] = email_counter
        self.time_counters[keyword] = time_counter
        
        return progress_bar
    
    def start_timer(self):
        """Démarre un timer qui s'actualise toutes les secondes"""
        self.start_time = time.time()
        
        def update_timer():
            if not self.stop_flag.is_set():
                elapsed = int(time.time() - self.start_time)
                self.timer_label.config(text=f"⏱ Temps: {elapsed}s")
                self.root.after(1000, update_timer)
        
        update_timer()
    
    def log(self, message):
        """Ajoute un message au log"""
        # Enlever les emojis pour éviter les problèmes d'encodage
        message = message.replace("🔍", "(recherche)").replace("📧", "(email)").replace("⚠️", "(attention)").replace("✅", "(ok)").replace("❌", "(erreur)").replace("📊", "(export)")
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        print(message)  # Aussi imprimer dans la console
    
    def export_to_excel(self):
        try:
            with sqlite3.connect('localch_data.db') as conn:
                # Proposer un chemin de fichier
                file_path = filedialog.asksaveasfilename(
                    initialdir=".",
                    title="Exporter en Excel",
                    defaultextension=".xlsx",
                    filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                    initialfile=f"local_ch_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                
                if not file_path:
                    return
                
                # Créer un ExcelWriter pour gérer plusieurs feuilles
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # D'abord, obtenir tous les mots-clés uniques
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT keyword FROM contacts ORDER BY keyword")
                    keywords = [row[0] for row in cursor.fetchall()]
                    
                    # Créer une feuille pour chaque mot-clé
                    for keyword in keywords:
                        # Obtenir les données pour ce mot-clé
                        query = """
                            SELECT 
                                name, address, phone, email, website, date_added 
                            FROM 
                                contacts 
                            WHERE 
                                keyword = ?
                            ORDER BY
                                name, email
                        """
                        df = pd.read_sql_query(query, conn, params=(keyword,))
                        
                        # Convertir les dates en format lisible
                        if 'date_added' in df.columns:
                            df['date_added'] = pd.to_datetime(df['date_added']).dt.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Renommer les colonnes pour plus de clarté
                        df.columns = ['Nom', 'Adresse', 'Téléphone', 'Email', 'Site Web', 'Date Ajout']
                        
                        # Écrire dans une feuille nommée d'après le mot-clé (limité à 31 caractères, limite Excel)
                        sheet_name = keyword[:31] if len(keyword) > 31 else keyword
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Créer une feuille récapitulative avec tous les résultats
                    all_query = """
                        SELECT 
                            keyword, name, address, phone, email, website, date_added
                        FROM 
                            contacts
                        ORDER BY
                            keyword, name, email
                    """
                    all_df = pd.read_sql_query(all_query, conn)
                    
                    # Convertir les dates en format lisible
                    if 'date_added' in all_df.columns:
                        all_df['date_added'] = pd.to_datetime(all_df['date_added']).dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Renommer les colonnes pour plus de clarté
                    all_df.columns = ['Mot-clé', 'Nom', 'Adresse', 'Téléphone', 'Email', 'Site Web', 'Date Ajout']
                    
                    # Écrire dans une feuille récapitulative
                    all_df.to_excel(writer, sheet_name='Tous les résultats', index=False)
                
                messagebox.showinfo("Succès", f"Données exportées vers {file_path}")
                self.log(f"(export) Données exportées vers {file_path} avec {len(keywords)} feuilles (une par mot-clé)")
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'export: {str(e)}")
            self.log(f"(erreur) Erreur lors de l'export: {str(e)}")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = LocalChScraper()
    app.run()
