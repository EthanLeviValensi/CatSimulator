import sys
import subprocess
import os
import random
import math 
import json
import time 

# --- Imports pour l'updater ---
import zipfile
import shutil
# --- Fin des imports pour l'updater ---

# --- Bootstrap pour PyQt6 ---
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel,
        QProgressBar, QPushButton, QHBoxLayout, QFrame, QDialog,
        QTextBrowser, QLineEdit
    )
    from PyQt6.QtGui import QMovie, QPixmap, QIcon, QCursor
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve
except ImportError:
    print("PyQt6 non trouvé. Tentative d'installation...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6"])
        print("PyQt6 installé avec succès.")
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel,
            QProgressBar, QPushButton, QHBoxLayout, QFrame, QDialog,
            QTextBrowser, QLineEdit
        )
        from PyQt6.QtGui import QMovie, QPixmap, QIcon, QCursor
        from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve
    except subprocess.CalledProcessError as e:
        print(f"Erreur fatale : Impossible d'installer PyQt6. Veuillez l'installer manuellement avec 'pip install PyQt6'. Détails : {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur inattendue lors de l'importation/installation de PyQt6: {e}")
        sys.exit(1)

# Variables globales qui seront définies par l'InstallWorker
GoogleTranslator = None
requests_module = None 

# ALERTE SÉCURITÉ: Pour une application de production, stockez ceci de manière plus sécurisée (variables d'environnement, config file externe).
HUGGING_FACE_API_TOKEN = "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" # REMPLACEZ CECI PAR VOTRE VRAI TOKEN HUGGING FACE

# Modèle Hugging Face à utiliser (Mistral-7B-Instruct-v0.2 est un bon choix pour le chat)
HUGGING_FACE_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
HUGGING_FACE_API_URL = f"https://api-inference.huggingface.co/models/{HUGGING_FACE_MODEL}"

# Ta clé d'API TheCatAPI
API_KEY = "live_McKZxmGzkewiGRwzf2IhXXXnpf3JEWQTooqzzRjqWPMTHJufrR87BXN3bPnJZZZo" # Votre clé TheCatAPI
SUB_ID = "my_awesome_cat_app_user"

# Nom du dossier pour les favoris
FAVORITES_FOLDER = "favoris"

# --- CONFIGURATION DU SYSTÈME DE MISE À JOUR ---
# REMPLACEZ CETTE LIGNE par l'URL de votre dossier 'updates' sur GitHub Pages !
UPDATE_SERVER_URL = "https://ethanlevivalensi.github.io/CatSimulator/updates/" # L'URL CORRIGÉE

LATEST_VERSION_FILE = "latest_version.txt"
GAME_ARCHIVE_PREFIX = "game_v" 
GAME_FOLDER_TO_UPDATE = "." 
LOCAL_VERSION_FILE = "version.txt" 
APPLY_UPDATE_SCRIPT_NAME = "apply_update_and_restart.py"

EXCLUDE_FROM_UPDATE_DELETION = [
    LOCAL_VERSION_FILE, 
    FAVORITES_FOLDER,   
    "loading_cat.gif",  
    "heart-filled.png", 
    "heart-outline.png",
    "chat_personalities.json" 
]
# --- FIN DE LA CONFIGURATION DU SYSTÈME DE MISE À JOUR ---


# --- THREAD DE CHARGEMENT DES DÉPENDANCES ---
class InstallWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress_status = pyqtSignal(str)
    progress_value = pyqtSignal(int)

    def run(self):
        global requests_module 
        global GoogleTranslator

        modules = ["requests", "deep_translator"]
        total_steps = len(modules) * 2
        current_step = 0

        for module in modules:
            self.progress_status.emit(f"Vérification de '{module}'...")
            current_step += 1
            self.progress_value.emit(int((current_step / total_steps) * 100))
            
            try:
                if module == "requests":
                    import requests as _temp_requests_module 
                    requests_module = _temp_requests_module 
                elif module == "deep_translator":
                    from deep_translator import GoogleTranslator as _temp_translator 
                    GoogleTranslator = _temp_translator 
                self.progress_status.emit(f"'{module}' est déjà installé.") 
            except ImportError:
                self.progress_status.emit(f"Installation de '{module}'...")
                current_step += 1
                self.progress_value.emit(int((current_step / total_steps) * 100))
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", module])
                    self.progress_status.emit(f"'{module}' installé avec succès.")
                    if module == "requests":
                        import requests as _temp_requests_module 
                        requests_module = _temp_requests_module 
                    elif module == "deep_translator":
                        from deep_translator import GoogleTranslator as _temp_translator 
                        GoogleTranslator = _temp_translator 
                except subprocess.CalledProcessError as e:
                    self.error.emit(f"Erreur lors de l'installation de '{module}': {e}. Veuillez installer manuellement.")
                    print(f"DEBUG: Erreur dans InstallWorker pour {module}: {e}") # Nouveau DEBUG
                    return
                except Exception as e:
                    self.error.emit(f"Erreur inattendue lors de l'installation de '{module}': {e}")
                    print(f"DEBUG: Erreur inattendue dans InstallWorker pour {module}: {e}") # Nouveau DEBUG
                    return
            current_step += 1
            self.progress_value.emit(int((current_step / total_steps) * 100))

        self.progress_status.emit("Installation des dépendances terminée.")
        self.progress_value.emit(100)
        QThread.msleep(500)
        self.finished.emit()
        print(f"DEBUG: InstallWorker terminé. requests_module (global) est: {requests_module}") # Nouveau DEBUG


# --- THREAD POUR LE GESTIONNAIRE DE MISES À JOUR ---
class UpdateManager(QThread):
    update_finished = pyqtSignal(bool) 
    update_error = pyqtSignal(str) 
    update_status_message = pyqtSignal(str) 
    update_progress_value = pyqtSignal(int) 

    def run(self):
        print("DEBUG: UpdateManager.run() démarré.") # Nouveau DEBUG
        self.update_status_message.emit("Vérification des mises à jour du jeu...")
        current_version = self._get_current_game_version()
        self.update_status_message.emit(f"Version locale du jeu : {current_version}")
        self.update_progress_value.emit(0)

        # Vérification critique de requests_module AVANT l'utilisation
        if requests_module is None: # Changé de 'not requests_module' pour plus de clarté
            error_msg = "Le module 'requests' n'est pas disponible pour la mise à jour. L'installation a-t-elle échoué ?"
            print(f"DEBUG ERROR: {error_msg} (requests_module est None)") # Nouveau DEBUG
            self.update_error.emit(error_msg)
            self.update_finished.emit(False)
            return
        else:
            print(f"DEBUG: requests_module est bien disponible : {requests_module}") # Nouveau DEBUG


        try:
            update_url = UPDATE_SERVER_URL + LATEST_VERSION_FILE
            self.update_status_message.emit(f"Tentative de connexion à {update_url} pour la dernière version...")
            print(f"DEBUG: Tentative de GET sur l'URL: {update_url}") # Debugging
            
            response = requests_module.get(update_url, timeout=10) # 10 secondes de timeout
            response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)

            # --- MESSAGE DE CONNEXION RÉUSSIE ---
            print("Connexion au serveur GitHub Pages réussie.")
            self.update_status_message.emit("Connexion au serveur de mise à jour réussie.")
            # -----------------------------------

            latest_version = response.text.strip()
            self.update_status_message.emit(f"Dernière version disponible : {latest_version}")
            self.update_progress_value.emit(20)

            # Conversion pour comparaison robuste
            # Pour gérer '0.9' < '1.0' correctement, nous devons traiter les versions comme des tuples
            # ou des objets comparables, pas juste des strings si les versions ont des points.
            # Cependant, pour des comparaisons simples comme '0.9' vs '1.0', la comparaison de chaînes fonctionne
            # si elles sont bien formatées. Si on passe à '1.10' après '1.9', la comparaison de chaînes ne marchera plus.
            # Pour l'instant, on suppose '1.0', '1.1', '1.2' etc.
            
            # Méthode plus robuste pour comparer des versions
            def parse_version(version_str):
                return tuple(map(int, version_str.split('.')))

            parsed_latest_version = parse_version(latest_version)
            parsed_current_version = parse_version(current_version)

            print(f"DEBUG: Versions Parsées: Locale={parsed_current_version}, Distante={parsed_latest_version}") # Nouveau DEBUG

            if parsed_latest_version > parsed_current_version:
                print(f"DEBUG: Nouvelle version ({latest_version}) trouvée. Démarrage du téléchargement.") # Nouveau DEBUG
                self.update_status_message.emit(f"Nouvelle version ({latest_version}) disponible. Téléchargement...")
                success = self._download_and_install_update(latest_version)
                if success:
                    self.update_status_message.emit("Mise à jour terminée. Veuillez redémarrer le jeu.")
                    self.update_progress_value.emit(100)
                    self.update_finished.emit(True) 
                else:
                    self.update_error.emit("Échec de l'installation de la mise à jour.")
                    self.update_finished.emit(False)
            else:
                print("DEBUG: Jeu déjà à jour ou version locale supérieure.") # Nouveau DEBUG
                self.update_status_message.emit("Votre jeu est déjà à jour.")
                self.update_progress_value.emit(100)
                self.update_finished.emit(False)

        except requests_module.exceptions.Timeout:
            error_msg = "Échec de la connexion au serveur de mise à jour (délai dépassé). Vérifiez votre connexion internet ou si le serveur est en ligne."
            print(f"DEBUG ERROR (Timeout): {error_msg}")
            self.update_error.emit(error_msg)
            self.update_finished.emit(False)
        except requests_module.exceptions.ConnectionError as e: # Capture l'exception pour plus de détails
            error_msg = f"Échec de la connexion au serveur de mise à jour (problème réseau ou serveur non disponible). Vérifiez votre connexion internet. Détails: {e}"
            print(f"DEBUG ERROR (ConnectionError): {error_msg}")
            self.update_error.emit(error_msg)
            self.update_finished.emit(False)
        except requests_module.exceptions.RequestException as e:
            error_msg = f"Une erreur HTTP s'est produite lors de la vérification des mises à jour : {e}. L'URL du dépôt GitHub Pages est-elle correcte ? Statut HTTP: {e.response.status_code if e.response else 'N/A'}"
            print(f"DEBUG ERROR (RequestException): {error_msg}")
            self.update_error.emit(error_msg)
            self.update_finished.emit(False)
        except Exception as e:
            error_msg = f"Une erreur inattendue est survenue lors de la vérification des mises à jour : {e}. Détails : {type(e).__name__}"
            print(f"DEBUG ERROR (Unhandled Exception in UpdateManager): {error_msg}")
            self.update_error.emit(error_msg)
            self.update_finished.emit(False)

    def _get_current_game_version(self):
        print(f"DEBUG: Lecture de la version locale depuis {LOCAL_VERSION_FILE}") # Nouveau DEBUG
        if os.path.exists(LOCAL_VERSION_FILE):
            try:
                with open(LOCAL_VERSION_FILE, "r") as f:
                    version = f.read().strip()
                    print(f"DEBUG: Version locale lue: {version} TESTTTTTTSTSTSTSTSTSTTSTSTSSTTSTSTSTSTSTSTSTSTSTSTSTSSTSTSTSTSTSTSTSTSSTSTST") # Nouveau DEBUG
                    return version
            except Exception as e:
                print(f"DEBUG ERROR: Impossible de lire le fichier de version locale: {e}") # Nouveau DEBUG
                return "0.0"
        print(f"DEBUG: Fichier de version locale '{LOCAL_VERSION_FILE}' non trouvé. Retourne '0.0'.") # Nouveau DEBUG
        return "0.0"

    def _update_local_game_version(self, new_version):
        try:
            with open(LOCAL_VERSION_FILE, "w") as f:
                f.write(new_version)
            self.update_status_message.emit(f"Version locale mise à jour vers {new_version}.")
            print(f"DEBUG: Fichier de version locale mis à jour vers {new_version}.") # Nouveau DEBUG
        except Exception as e:
            self.update_error.emit(f"Erreur lors de l'écriture du fichier de version local : {e}")
            print(f"DEBUG ERROR: Erreur lors de l'écriture du fichier de version local: {e}") # Nouveau DEBUG

    def _download_and_install_update(self, new_version):
        print(f"DEBUG: Démarrage du téléchargement et installation de la mise à jour pour la version {new_version}")
        archive_name = f"{GAME_ARCHIVE_PREFIX}{new_version.replace('.', '_')}.zip"
        download_url = UPDATE_SERVER_URL + archive_name
        temp_dir = os.path.join(os.getcwd(), "update_temp_staging") # Nouveau dossier temporaire

        # On ajoute le nouveau main.py à télécharger séparément
        new_main_py_url = UPDATE_SERVER_URL + "main.py" # Assurez-vous que main.py est disponible directement à cette URL
        new_main_py_temp_path = os.path.join(temp_dir, "main.py")

        try:
            # Créer le dossier temporaire de staging
            os.makedirs(temp_dir, exist_ok=True)
            print(f"DEBUG: Dossier temporaire de mise à jour créé: {temp_dir}")

            self.update_status_message.emit(f"Téléchargement de '{archive_name}'...")
            print(f"DEBUG: Téléchargement du jeu depuis: {download_url}")
            response = requests_module.get(download_url, stream=True, timeout=600)
            response.raise_for_status()

            temp_archive_path = os.path.join(temp_dir, archive_name) # L'archive est téléchargée dans temp_dir
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            with open(temp_archive_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if total_size > 0:
                        self.update_progress_value.emit(20 + int((bytes_downloaded / total_size) * 30)) # Ajustement de la progression

            self.update_status_message.emit("Téléchargement du jeu terminé.")
            self.update_progress_value.emit(50)
            print("DEBUG: Téléchargement du jeu terminé.")

            self.update_status_message.emit("Téléchargement de la nouvelle version du lanceur (main.py)...")
            print(f"DEBUG: Téléchargement du nouveau main.py depuis: {new_main_py_url}")
            response_main = requests_module.get(new_main_py_url, timeout=30)
            response_main.raise_for_status()
            with open(new_main_py_temp_path, 'wb') as f:
                f.write(response_main.content)
            self.update_status_message.emit("Nouvelle version du lanceur téléchargée.")
            self.update_progress_value.emit(60)
            print("DEBUG: Nouvelle version du lanceur (main.py) téléchargée.")

            self.update_status_message.emit("Décompression de la mise à jour...")
            with zipfile.ZipFile(temp_archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir) # Décompression dans le dossier temporaire
            self.update_status_message.emit("Décompression terminée.")
            self.update_progress_value.emit(70)
            print("DEBUG: Décompression terminée.")

            # --- Création du script d'aide pour l'application de la mise à jour ---
            apply_update_script_path = os.path.join(os.getcwd(), APPLY_UPDATE_SCRIPT_NAME)
            current_main_path = os.path.abspath(__file__) # Chemin absolu de main.py

            # ATTENTION: Le chemin est important ici ! Utilisez os.path.abspath()
            script_content = f"""
import os
import sys
import shutil
import time

# Attendre un peu que le programme principal se ferme complètement
time.sleep(2) # Ajustez si nécessaire, peut être plus long sur des machines lentes

print(f"APPLY_UPDATE: Script '{APPLY_UPDATE_SCRIPT_NAME}' démarré.")
print(f"APPLY_UPDATE: Dossier courant: {{os.getcwd()}}")

game_folder_to_update = "{os.path.abspath(GAME_FOLDER_TO_UPDATE).replace(os.sep, '/')}" # Chemin du dossier du jeu
temp_extract_path = "{os.path.abspath(temp_dir).replace(os.sep, '/')}" # Chemin du dossier temporaire
local_version_file = "{LOCAL_VERSION_FILE}"
favorites_folder = "{FAVORITES_FOLDER}"
apply_update_script = "{APPLY_UPDATE_SCRIPT_NAME}"
current_main_file = "{os.path.basename(current_main_path)}" # Nom du fichier main.py

exclude_from_deletion = [
    os.path.basename(local_version_file),
    os.path.basename(favorites_folder),
    os.path.basename(apply_update_script), # Exclure le script d'aide lui-même
    os.path.basename(current_main_file), # Le main.py actuel sera remplacé, pas supprimé avant ça
    "loading_cat.gif", # Exclure aussi du nettoyage si vous ne les mettez pas dans le zip
    "heart-filled.png",
    "heart-outline.png",
    "chat_personalities.json",
    # Ajoutez ici tous les fichiers ou dossiers que vous NE VOULEZ JAMAIS supprimer, même s'ils ne sont pas dans le zip
]

print("APPLY_UPDATE: Suppression des anciens fichiers (sauf exclus)...")
for item in os.listdir(game_folder_to_update):
    item_path = os.path.join(game_folder_to_update, item)
    if item not in exclude_from_deletion:
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
                print(f"APPLY_UPDATE: Supprimé fichier: {{item_path}}")
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"APPLY_UPDATE: Supprimé dossier: {{item_path}}")
        except Exception as e:
            print(f"APPLY_UPDATE ERROR: Erreur lors de la suppression de '{{item_path}}': {{e}}")

print("APPLY_UPDATE: Copie des nouveaux fichiers depuis le dossier temporaire...")
for item in os.listdir(temp_extract_path):
    s = os.path.join(temp_extract_path, item)
    d = os.path.join(game_folder_to_update, item)
    try:
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d) # Supprime l'ancien dossier avant de copier le nouveau
            shutil.copytree(s, d)
            print(f"APPLY_UPDATE: Copié dossier: {{s}} vers {{d}}")
        else:
            shutil.copy2(s, d) # copy2 conserve les métadonnées (permissions, etc.)
            print(f"APPLY_UPDATE: Copié fichier: {{s}} vers {{d}}")
    except Exception as e:
        print(f"APPLY_UPDATE ERROR: Erreur lors de la copie de '{{s}}' vers '{{d}}': {{e}}")

# Mise à jour du fichier de version locale (après la copie des fichiers)
new_version_to_write = "{new_version}"
try:
    with open(os.path.join(game_folder_to_update, local_version_file), "w") as f:
        f.write(new_version_to_write)
    print(f"APPLY_UPDATE: Fichier de version locale mis à jour vers {{new_version_to_write}}.")
except Exception as e:
    print(f"APPLY_UPDATE ERROR: Erreur lors de l'écriture du fichier de version locale: {{e}}")

print("APPLY_UPDATE: Nettoyage du dossier temporaire...")
try:
    shutil.rmtree(temp_extract_path)
    print(f"APPLY_UPDATE: Supprimé dossier temporaire: {{temp_extract_path}}")
except Exception as e:
    print(f"APPLY_UPDATE ERROR: Impossible de supprimer le dossier temporaire '{{temp_extract_path}}': {{e}}")

print("APPLY_UPDATE: Mise à jour terminée. Relancement du jeu...")
# Relancer le main.py mis à jour
try:
    subprocess.Popen([sys.executable, os.path.join(game_folder_to_update, current_main_file)])
except Exception as e:
    print(f"APPLY_UPDATE ERROR: Impossible de relancer le jeu: {{e}}")
"""
            with open(apply_update_script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            print(f"DEBUG: Script d'aide '{APPLY_UPDATE_SCRIPT_NAME}' créé.")

            self.update_status_message.emit("Mise à jour prête. Redémarrage de l'application...")
            self.update_progress_value.emit(100)
            print("DEBUG: Application principale va se fermer pour appliquer la mise à jour et relancer.")
            
            # Lancer le script d'aide en arrière-plan et quitter l'application principale
            subprocess.Popen([sys.executable, apply_update_script_path], 
                             creationflags=subprocess.DETACHED_PROCESS if os.name == 'nt' else 0,
                             close_fds=True) # close_fds=True pour Linux/macOS
            
            # Indiquer à l'écran de chargement de se fermer
            QTimer.singleShot(100, lambda: self.update_finished.emit(True)) # Indique une mise à jour réussie
            return True

        except requests_module.exceptions.Timeout:
            error_msg = "Le téléchargement de la mise à jour a expiré. Annulation."
            self.update_error.emit(error_msg)
            print(f"DEBUG ERROR (Download Timeout): {error_msg}")
        except requests_module.exceptions.ConnectionError as e:
            error_msg = f"Problème de connexion lors du téléchargement. Annulation. Détails: {e}"
            self.update_error.emit(error_msg)
            print(f"DEBUG ERROR (Download ConnectionError): {error_msg}")
        except requests_module.exceptions.RequestException as e:
            error_msg = f"Erreur HTTP lors du téléchargement de la mise à jour : {e}. Annulation."
            self.update_error.emit(error_msg)
            print(f"DEBUG ERROR (Download RequestException): {error_msg}")
        except zipfile.BadZipFile:
            error_msg = "Le fichier de mise à jour téléchargé est corrompu. Annulation."
            self.update_error.emit(error_msg)
            print(f"DEBUG ERROR (BadZipFile): {error_msg}")
        except Exception as e:
            error_msg = f"Une erreur inattendue est survenue lors de l'installation : {e}. Annulation."
            self.update_error.emit(error_msg)
            print(f"DEBUG ERROR (Unhandled Exception in Download/Install): {e}. Annulation.")
        finally:
            # Le nettoyage des fichiers temporaires sera fait par le script d'aide, pas ici.
            pass
        return False
    
    def _cleanup_temp_files(self, archive_path, extract_path):
        self.update_status_message.emit("Nettoyage des fichiers temporaires...")
        if os.path.exists(archive_path):
            try:
                os.remove(archive_path)
                print(f"DEBUG: Supprimé archive temporaire: {archive_path}") # Nouveau DEBUG
            except Exception as e:
                self.update_status_message.emit(f"Impossible de supprimer l'archive temporaire '{archive_path}': {e}")
                print(f"DEBUG ERROR: Impossible de supprimer l'archive temporaire: {e}") # Nouveau DEBUG
        if os.path.exists(extract_path):
            try:
                shutil.rmtree(extract_path)
                print(f"DEBUG: Supprimé dossier d'extraction temporaire: {extract_path}") # Nouveau DEBUG
            except Exception as e:
                self.update_status_message.emit(f"Impossible de supprimer le dossier d'extraction temporaire '{extract_path}': {e}")
                print(f"DEBUG ERROR: Impossible de supprimer le dossier d'extraction temporaire: {e}") # Nouveau DEBUG
        self.update_status_message.emit("Nettoyage terminé.")


# --- ÉCRAN DE CHARGEMENT INITIAL ---
class LoadingScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chargement du Générateur de Chats")
        self.setFixedSize(500, 400)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(20)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: white;
            }
            QLabel#loadingTitle {
                color: #bb86fc;
                font-size: 30px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QLabel#gifLabel {
                border-radius: 10px;
                background-color: #2c2c2c;
            }
            QLabel#statusLabel {
                color: #cccccc;
                font-size: 14px;
            }
            QProgressBar {
                height: 20px;
                text-align: center;
                border: 1px solid #bb86fc;
                border-radius: 10px;
                background-color: #3a3a3a;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #bb86fc, stop:1 #9f6ee6);
                border-radius: 9px;
            }
            QPushButton {
                background-color: #bb86fc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                /* Supprimé: transition: background-color 0.3s ease; */
            }
            QPushButton:hover {
                background-color: #9f6ee6;
            }
            QPushButton:disabled {
                background-color: #607D8B;
                color: #B0BEC5;
                /* Supprimé: cursor: default; */
            }
        """)

        self.title_label = QLabel("Générateur de Chats")
        self.title_label.setObjectName("loadingTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title_label)

        self.gif_label = QLabel()
        self.gif_label.setObjectName("gifLabel")
        self.movie = QMovie("loading_cat.gif")
        if not self.movie.isValid():
            print("Avertissement: loading_cat.gif non trouvé ou invalide. Veuillez fournir un GIF.")
            self.gif_label.setText("Chargement...")
            self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.gif_label.setStyleSheet("color: white; font-size: 18px; background-color: transparent;")
        else:
            self.movie.setScaledSize(QSize(120, 120))
            self.gif_label.setMovie(self.movie)
            self.movie.start()
        self.layout.addWidget(self.gif_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Initialisation des dépendances...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

        self.install_worker = InstallWorker()
        self.install_worker.finished.connect(self.on_installation_finished) 
        self.install_worker.error.connect(self.on_initial_error)
        self.install_worker.progress_status.connect(self.update_status)
        self.install_worker.progress_value.connect(self.update_progress_install)
        print("DEBUG: Lancement de InstallWorker.") # Nouveau DEBUG
        self.install_worker.start()

        self.update_manager = None
        self.cat_generator_app = None

    def update_status(self, message):
        self.status_label.setText(message)

    def update_progress_install(self, value):
        self.progress_bar.setValue(int(value * 0.5))

    def update_progress_update(self, value):
        self.progress_bar.setValue(50 + int(value * 0.5))

    def on_installation_finished(self):
        print("DEBUG: InstallWorker.finished déclenché. Lancement de UpdateManager.") # Nouveau DEBUG
        self.status_label.setText("Dépendances prêtes. Vérification des mises à jour du jeu...")
        self.update_manager = UpdateManager()
        self.update_manager.update_finished.connect(self.on_update_check_finished)
        self.update_manager.update_error.connect(self.on_initial_error) 
        self.update_manager.update_status_message.connect(self.update_status)
        self.update_manager.update_progress_value.connect(self.update_progress_update)
        self.update_manager.start()

    def on_update_check_finished(self, update_performed: bool):
        print(f"DEBUG: UpdateManager.update_finished déclenché. Mise à jour effectuée: {update_performed}")
        if update_performed:
            self.status_label.setText("Mise à jour terminée. Redémarrage de l'application...")
            self.progress_bar.setValue(100)
            # La mise à jour est lancée par le script d'aide. Il faut juste quitter l'application actuelle.
            QTimer.singleShot(1000, self.close) # Donne un peu de temps au message d'apparaître
        else:
            self.status_label.setText("Jeu à jour. Lancement de l'application...")
            self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
            self.fade_out_animation.setDuration(500)
            self.fade_out_animation.setStartValue(1.0)
            self.fade_out_animation.setEndValue(0.0)
            self.fade_out_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.fade_out_animation.finished.connect(self.launch_main_app)
            self.fade_out_animation.start()

    def launch_main_app(self):
        print("DEBUG: Lancement de l'application principale CatGeneratorApp.") # Nouveau DEBUG
        _requests_is_ready = requests_module is not None
        _deep_translator_is_ready = GoogleTranslator is not None
        self.cat_generator_app = CatGeneratorApp(_requests_is_ready, _deep_translator_is_ready)
        self.cat_generator_app.show()
        self.close()

    def on_initial_error(self, message):
        print(f"DEBUG: Erreur fatale initiale: {message}") # Nouveau DEBUG
        self.status_label.setText(f"Erreur fatale: {message}")
        self.progress_bar.setValue(0)
        close_button = QPushButton("Quitter")
        close_button.clicked.connect(self.close)
        self.layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignCenter)

# --- THREAD DE CHARGEMENT DES DONNÉES DU CHAT ---
class CatDataWorker(QThread):
    data_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()

    def run(self):
        if not requests_module:
            self.error_occurred.emit("Le module 'requests' n'est pas disponible pour charger les données.")
            print("DEBUG ERROR: requests_module n'est pas disponible dans CatDataWorker.") # Nouveau DEBUG
            return

        api_url = "https://api.thecatapi.com/v1/images/search?has_breeds=1"
        headers = {
            "x-api-key": API_KEY
        }
        
        try:
            print(f"DEBUG: CatDataWorker - Tentative de GET sur l'API TheCatAPI: {api_url}") # Nouveau DEBUG
            response = requests_module.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            print("DEBUG: CatDataWorker - Données reçues de TheCatAPI.") # Nouveau DEBUG

            if data and isinstance(data, list) and len(data) > 0:
                cat_info = data[0]
                image_url = cat_info.get('url')
                image_id = cat_info.get('id')
                
                breed_name = 'Race inconnue'
                breed_description = 'Description non disponible.'
                wikipedia_url = None

                breeds = cat_info.get('breeds')
                if breeds and isinstance(breeds, list) and len(breeds) > 0:
                    breed_info = breeds[0]
                    breed_name = breed_info.get('name', 'Race inconnue')
                    breed_description = breed_info.get('description', 'Description non disponible.')
                    wikipedia_url = breed_info.get('wikipedia_url')
                
                image_data = None
                if image_url:
                    print(f"DEBUG: CatDataWorker - Téléchargement de l'image depuis: {image_url}") # Nouveau DEBUG
                    image_response = requests_module.get(image_url)
                    image_response.raise_for_status()
                    image_data = image_response.content
                    print("DEBUG: CatDataWorker - Image téléchargée.") # Nouveau DEBUG

                self.data_loaded.emit({
                    "image_id": image_id,
                    "image_url": image_url,
                    "image_data": image_data,
                    "breed_name": breed_name,
                    "breed_description": breed_description,
                    "wikipedia_url": wikipedia_url
                })
            else:
                self.error_occurred.emit("Aucune donnée de chat trouvée depuis l'API.")
                print("DEBUG ERROR: CatDataWorker - Aucune donnée de chat trouvée.") # Nouveau DEBUG

        except requests_module.exceptions.RequestException as e:
            error_msg = f"Erreur réseau lors du chargement des données du chat: {e}"
            self.error_occurred.emit(error_msg)
            print(f"DEBUG ERROR: CatDataWorker - {error_msg}") # Nouveau DEBUG
        except Exception as e:
            error_msg = f"Une erreur inattendue est survenue lors du chargement: {e}"
            self.error_occurred.emit(error_msg)
            print(f"DEBUG ERROR: CatDataWorker - {error_msg}") # Nouveau DEBUG

# --- NOUVEAU THREAD POUR LE CHATBOT ---
class ChatbotWorker(QThread):
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, user_message: str, chat_prompt_context: str):
        super().__init__()
        self.user_message = user_message
        self.chat_prompt_context = chat_prompt_context

    def run(self):
        if not requests_module:
            self.error_occurred.emit("Le module 'requests' n'est pas disponible pour le chatbot.")
            print("DEBUG ERROR: requests_module n'est pas disponible dans ChatbotWorker.") # Nouveau DEBUG
            return
        if not HUGGING_FACE_API_TOKEN or HUGGING_FACE_API_TOKEN == "YOUR_HUGGING_FACE_API_TOKEN":
            self.error_occurred.emit("Le token d'API Hugging Face n'est pas configuré. Veuillez le remplacer dans le code.")
            print("DEBUG ERROR: Token Hugging Face non configuré.") # Nouveau DEBUG
            return

        headers = {
            "Authorization": f"Bearer {HUGGING_FACE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        messages = [
            {"role": "system", "content": self.chat_prompt_context},
            {"role": "user", "content": self.user_message}
        ]

        payload = {
            "inputs": messages,
            "parameters": {
                "max_new_tokens": 150,
                "temperature": 0.7,
                "top_p": 0.9,
                "repetition_penalty": 1.2
            },
            "options": {
                "use_cache": False
            }
        }

        api_url_to_print = f"https://api-inference.huggingface.co/models/{HUGGING_FACE_MODEL}"
        print(f"DEBUG HF API URL: {api_url_to_print}")

        try:
            print(f"DEBUG: ChatbotWorker - Tentative de POST sur l'API Hugging Face.") # Nouveau DEBUG
            response = requests_module.post(HUGGING_FACE_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            print("DEBUG: ChatbotWorker - Réponse reçue de l'API Hugging Face.") # Nouveau DEBUG

            if result and isinstance(result, list) and len(result) > 0 and 'generated_text' in result[0]:
                chat_response = result[0]['generated_text'].strip()
                
                if chat_response.endswith("</s>"):
                    chat_response = chat_response[:-4].strip()
                if chat_response.startswith("Chat:"):
                    chat_response = chat_response[len("Chat:"):].strip()

                self.response_received.emit(chat_response)
            else:
                self.error_occurred.emit("Réponse inattendue de l'API Hugging Face.")
                print("DEBUG ERROR: ChatbotWorker - Réponse inattendue de l'API Hugging Face.") # Nouveau DEBUG
        except requests_module.exceptions.RequestException as e:
            error_msg = f"Erreur réseau ou API Hugging Face: {e}"
            self.error_occurred.emit(error_msg)
            print(f"DEBUG ERROR: ChatbotWorker - {error_msg}") # Nouveau DEBUG
        except json.JSONDecodeError:
            error_msg = "Erreur de décodage JSON de la réponse de l'API."
            self.error_occurred.emit(error_msg)
            print(f"DEBUG ERROR: ChatbotWorker - {error_msg}") # Nouveau DEBUG
        except Exception as e:
            error_msg = f"Une erreur inattendue est survenue avec le chatbot: {e}"
            self.error_occurred.emit(error_msg)
            print(f"DEBUG ERROR: ChatbotWorker - {error_msg}") # Nouveau DEBUG


# --- NOUVELLE FENÊTRE DE DIALOGUE CHATBOT ---
class ChatbotWindow(QDialog):
    def __init__(self, parent=None, breed_name: str = "", breed_description: str = "", personality_instructions: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"Parle au chat ({breed_name})")
        self.setGeometry(200, 200, 500, 600)
        self.setModal(True)

        self.breed_name = breed_name
        self.breed_description = breed_description
        self.personality_instructions = personality_instructions
        
        self.chat_context = f"Tu es un chat de race {self.breed_name}. Voici une description de ta race : {self.breed_description}. {self.personality_instructions}"
        self.chat_history = [] 

        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: white;
                border-radius: 10px;
                border: 1px solid #bb86fc;
            }
            QTextBrowser {
                background-color: #2c2c2c;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #5a5a5a;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #bb86fc;
            }
            QPushButton {
                background-color: #bb86fc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                /* Supprimé: transition: background-color 0.3s ease; */
            }
            QPushButton:hover {
                background-color: #9f6ee6;
            }
            QPushButton:disabled {
                background-color: #607D8B;
                color: #B0BEC5;
                /* Supprimé: cursor: default; */
            }
            QLabel#statusMessage {
                color: #ff5555;
                font-size: 13px;
                min-height: 15px;
            }
            QTextBrowser p {
                margin-bottom: 5px;
            }
            QTextBrowser b {
                font-weight: bold;
            }
        """)

        self.chat_history_display = QTextBrowser()
        self.chat_history_display.setReadOnly(True)
        self.layout.addWidget(self.chat_history_display)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Tapez votre message ici...")
        self.message_input.returnPressed.connect(self.send_message)
        self.layout.addWidget(self.message_input)

        self.send_button = QPushButton("Envoyer")
        self.send_button.clicked.connect(self.send_message)
        self.layout.addWidget(self.send_button)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusMessage")
        self.layout.addWidget(self.status_label)

        self.append_message("Chat", f"Miaou ! Je suis un {self.breed_name}. {self.personality_instructions.split('.')[0]}. Que veux-tu, humain ?")

    def append_message(self, sender: str, message: str, color: str = "white"):
        if sender == "Humain":
            formatted_message = f"<p style='color:#bb86fc; margin-bottom: 5px;'><b>Humain:</b> <span style='color:{color};'>{message}</span></p>"
        else:
            formatted_message = f"<p style='color:#4CAF50; margin-bottom: 5px;'><b>{sender}:</b> <span style='color:{color};'>{message}</span></p>"
        self.chat_history_display.append(formatted_message)
        self.chat_history_display.verticalScrollBar().setValue(self.chat_history_display.verticalScrollBar().maximum())


    def send_message(self):
        user_text = self.message_input.text().strip()
        if not user_text:
            return

        self.append_message("Humain", user_text)
        self.message_input.clear()
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.status_label.setText("Le chat réfléchit...")

        self.chatbot_worker = ChatbotWorker(user_text, self.chat_context)
        self.chatbot_worker.response_received.connect(self.handle_chatbot_response)
        self.chatbot_worker.error_occurred.connect(self.handle_chatbot_error)
        self.chatbot_worker.finished.connect(self.on_chatbot_finished)
        self.chatbot_worker.start()

    def handle_chatbot_response(self, response_text: str):
        self.append_message("Chat", response_text)
        self.chat_history.append({"sender": "Humain", "message": self.message_input.text()})
        self.chat_history.append({"sender": "Chat", "message": response_text})
        self.status_label.setText("")

    def handle_chatbot_error(self, error_message: str):
        self.append_message("Chat", f"Désolé, je suis un peu fatigué et je ne peux pas répondre... ({error_message})", "red")
        self.status_label.setText(f"Erreur: {error_message}")

    def on_chatbot_finished(self):
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.message_input.setFocus()


# --- APPLICATION PRINCIPALE ---
class CatGeneratorApp(QMainWindow):
    def __init__(self, requests_available: bool, deep_translator_available: bool):
        super().__init__()
        self.setWindowTitle("Générateur de Chats Mignon")
        self.setGeometry(100, 100, 800, 600)

        self.current_cat_breed_name = None
        self.current_cat_breed_description = None
        self.current_cat_image_id = None
        self.current_cat_image_url = None
        self.is_liked = False

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: white;
            }
            QWidget {
                background-color: #2c2c2c;
                border-radius: 10px;
            }
            QLabel {
                color: #e0e0e0;
                font-family: Arial, sans-serif;
            }
            QLabel#catImageLabel {
                border: 2px solid #bb86fc;
                border-radius: 10px;
                background-color: #3a3a3a;
            }
            QLabel#catBreedLabel {
                color: #bb86fc;
                font-size: 22px;
                font-weight: bold;
                text-align: center;
                padding-top: 10px;
            }
            QLabel#catDescriptionLabel {
                color: #cccccc;
                font-size: 14px;
                line-height: 1.5;
            }
            QPushButton {
                background-color: #bb86fc;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                /* Supprimé: transition: background-color 0.3s ease; */
            }
            QPushButton:hover {
                background-color: #9f6ee6;
            }
            QFrame#separator {
                background-color: #4a4a4a;
                height: 1px;
            }
            QPushButton#likeButton {
                background-color: #4a4a4a;
                border-radius: 25px;
                padding: 10px;
                width: 50px;
                height: 50px;
                qproperty-iconSize: 30px;
                color: white;
            }
            
            QPushButton#likeButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton#saveButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton#saveButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #607D8B;
                color: #B0BEC5;
                /* Supprimé: cursor: default; */
            }
            QLabel#statusMessage {
                color: #4CAF50;
                font-size: 14px;
                font-weight: bold;
                margin-top: 5px;
                min-height: 20px;
            }
        """)

        self.cat_image_label = QLabel("Chargement de l'image...")
        self.cat_image_label.setObjectName("catImageLabel")
        self.cat_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cat_image_label.setFixedSize(400, 300)
        self.layout.addWidget(self.cat_image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.cat_breed_label = QLabel("Nom de la race")
        self.cat_breed_label.setObjectName("catBreedLabel")
        self.cat_breed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.cat_breed_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("separator")
        self.layout.addWidget(separator)

        self.cat_description_label = QLabel("Description de la race")
        self.cat_description_label.setObjectName("catDescriptionLabel")
        self.cat_description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.cat_description_label.setWordWrap(True)
        self.cat_description_label.setTextFormat(Qt.TextFormat.RichText)
        self.layout.addWidget(self.cat_description_label)

        self.status_message_label = QLabel("")
        self.status_message_label.setObjectName("statusMessage")
        self.status_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_message_label)
        self.status_message_timer = QTimer(self)
        self.status_message_timer.setSingleShot(True)
        self.status_message_timer.timeout.connect(lambda: self.status_message_label.setText(""))

        self.button_layout = QHBoxLayout()
        self.button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.new_cat_button = QPushButton("Nouveau Chat")
        self.new_cat_button.clicked.connect(self.start_cat_data_loading)
        self.button_layout.addWidget(self.new_cat_button)

        self.like_button = QPushButton()
        self.like_button.setObjectName("likeButton")
        self.set_like_button_icon_or_text(False)
        self.like_button.clicked.connect(self.toggle_like)
        self.button_layout.addWidget(self.like_button)

        self.save_button = QPushButton("Enregistrer")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self.save_cat_image)
        self.button_layout.addWidget(self.save_button)

        self.layout.addLayout(self.button_layout)

        self.requests_module = requests_module 
        self.translator = None
        if GoogleTranslator:
            self.translator = GoogleTranslator(source='en', target='fr')
        else:
            print("Avertissement: deep_translator n'est pas disponible. Les descriptions ne seront pas traduites.")

        os.makedirs(FAVORITES_FOLDER, exist_ok=True)
        print(f"Dossier des favoris : {os.path.abspath(FAVORITES_FOLDER)}")

        self.cat_personalities = []
        try:
            with open("chat_personalities.json", "r", encoding="utf-8") as f:
                self.cat_personalities = json.load(f)
            print(f"Chargement de {len(self.cat_personalities)} personnalités de chat.")
        except FileNotFoundError:
            print("Erreur: Fichier 'chat_personalities.json' non trouvé. Le chatbot aura une personnalité par défaut.")
            self.cat_personalities = [{"name": "par défaut", "instructions": "Tu es un chat amical."}]
        except json.JSONDecodeError:
            print("Erreur: Fichier 'chat_personalities.json' mal formé. Le chatbot aura une personnalité par défaut.")
            self.cat_personalities = [{"name": "par défaut", "instructions": "Tu es un chat amical."}]


        if self.requests_module:
            self.start_cat_data_loading()
        else:
            self.cat_image_label.setText("Impossible de charger les images: 'requests' n'est pas disponible.")
            self.new_cat_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.save_button.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            self.like_button.setEnabled(False)

    def set_like_button_icon_or_text(self, liked: bool):
        if not QIcon("heart-filled.png").isNull() and not QIcon("heart-outline.png").isNull():
            if liked:
                self.like_button.setIcon(QIcon("heart-filled.png"))
            else:
                self.like_button.setIcon(QIcon("heart-outline.png"))
        else:
            self.like_button.setText("❤️" if liked else "🤍")
            self.like_button.setStyleSheet(f"QPushButton#likeButton {{ background-color: #4a4a4a; border-radius: 25px; padding: 10px; width: 50px; height: 50px; qproperty-iconSize: 30px; color: {'#e04a5a' if liked else 'white'}; }}"
                                            "QPushButton#likeButton:hover { background-color: #5a5a5a; }")

    def set_like_button_state(self, liked: bool):
        self.is_liked = liked
        self.like_button.setProperty("liked", "true" if liked else "false")
        self.like_button.style().polish(self.like_button)
        self.set_like_button_icon_or_text(liked)

    def start_cat_data_loading(self):
        if not self.requests_module:
            self.show_status_message("Erreur: Le module 'requests' n'est pas disponible.", "red")
            return
        
        self.cat_image_label.setText("Chargement de l'image...")
        self.cat_image_label.setPixmap(QPixmap())
        self.cat_breed_label.setText("Chargement de la race...")
        self.cat_description_label.setText("Chargement de la description...")
        self.current_cat_image_id = None
        self.current_cat_image_url = None
        self.current_cat_breed_name = None
        self.current_cat_breed_description = None
        self.set_like_button_state(False)
        self.status_message_label.setText("")

        self.new_cat_button.setEnabled(False)
        self.new_cat_button.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        self.save_button.setEnabled(False)
        self.save_button.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        self.like_button.setEnabled(False)
        self.like_button.setCursor(QCursor(Qt.CursorShape.WaitCursor))

        self.cat_data_worker = CatDataWorker()
        self.cat_data_worker.data_loaded.connect(self.on_cat_data_loaded)
        self.cat_data_worker.error_occurred.connect(self.on_cat_data_error)
        self.cat_data_worker.finished.connect(self.on_cat_data_loading_finished)
        self.cat_data_worker.start()

    def on_cat_data_loaded(self, cat_data):
        self.current_cat_image_id = cat_data.get('image_id')
        self.current_cat_image_url = cat_data.get('image_url')
        self.current_cat_breed_name = cat_data.get('breed_name')
        self.current_cat_breed_description = cat_data.get('breed_description', 'Description non disponible.')

        if cat_data.get('image_data'):
            pixmap = QPixmap()
            pixmap.loadFromData(cat_data['image_data'])
            scaled_pixmap = pixmap.scaled(self.cat_image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cat_image_label.setPixmap(scaled_pixmap)
        else:
            self.cat_image_label.setText("Image non disponible.")

        breed_name = cat_data.get('breed_name', 'Race inconnue')
        breed_description = cat_data.get('breed_description', 'Description non disponible.')
        wikipedia_url = cat_data.get('wikipedia_url')

        self_description_label_text = breed_description
        if self.translator and breed_description != 'Description non disponible.':
            try:
                translated_description = self.translator.translate(breed_description)
                self_description_label_text = translated_description
            except Exception as e:
                print(f"Erreur lors de la traduction: {e}. Affichage de la description originale.")
                self_description_label_text = breed_description
        else:
            if not GoogleTranslator:
                 print("Deep_translator n'est pas disponible, donc la traduction ne sera pas effectuée.")

        self.cat_breed_label.setText(breed_name)

        if wikipedia_url:
            html_description = f"{self_description_label_text}<br><br><a href='{wikipedia_url}' style='color: #bb86fc; text-decoration: none;'>En savoir plus sur Wikipédia</a>"
            self.cat_description_label.setText(html_description)
            self.cat_description_label.setOpenExternalLinks(True)
        else:
            self.cat_description_label.setText(self_description_label_text)

        if self.current_cat_image_url:
            self.save_button.setEnabled(True)
            self.save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.save_button.setEnabled(False)
            self.save_button.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))

    def on_cat_data_error(self, message):
        self.cat_image_label.setText("Erreur de chargement.")
        self.cat_breed_label.setText("Erreur")
        self.cat_description_label.setText(message)
        self.show_status_message(f"Échec du chargement : {message}", "red")
        
        self.save_button.setEnabled(False)
        self.save_button.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))

    def on_cat_data_loading_finished(self):
        self.new_cat_button.setEnabled(True)
        self.new_cat_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.like_button.setEnabled(True)
        self.like_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def toggle_like(self):
        if not self.requests_module:
            self.show_status_message("Erreur: Le module 'requests' n'est pas disponible.", "red")
            return
        if not self.current_cat_image_id:
            self.show_status_message("Aucune image à liker.", "red")
            return

        if self.is_liked:
            self.unlike_cat()
        else:
            self.like_cat()

    def like_cat(self):
        if not self.requests_module:
            return

        if not self.current_cat_image_id:
            return

        api_url = "https://api.thecatapi.com/v1/favourites"
        headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "image_id": self.current_cat_image_id,
            "sub_id": SUB_ID
        }

        try:
            response = self.requests_module.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            if result.get("message") == "SUCCESS":
                self.show_status_message("Chat liké avec succès !", "green")
                self.set_like_button_state(True)
                self.open_chatbot_window()
            else:
                self.show_status_message(f"Échec du like : {result.get('message')}", "red")
        except self.requests_module.exceptions.RequestException as e:
            self.show_status_message(f"Erreur réseau lors du like : {e}", "red")
        except Exception as e:
            self.show_status_message(f"Erreur inattendue lors du like : {e}", "red")

    def open_chatbot_window(self):
        if not requests_module:
            self.show_status_message("Erreur: Le chatbot nécessite le module 'requests'.", "red")
            return
        if not HUGGING_FACE_API_TOKEN or HUGGING_FACE_API_TOKEN == "YOUR_HUGGING_FACE_API_TOKEN":
            self.show_status_message("Erreur: Token Hugging Face non configuré pour le chatbot. Veuillez le mettre à jour.", "red")
            return
        if not self.current_cat_breed_name or not self.current_cat_breed_description:
            self.show_status_message("Impossible d'ouvrir le chatbot: données de race manquantes.", "red")
            return
        
        selected_personality = random.choice(self.cat_personalities)
        personality_instructions = selected_personality["instructions"]

        chatbot_dialog = ChatbotWindow(
            self,
            self.current_cat_breed_name,
            self.current_cat_breed_description,
            personality_instructions
        )
        chatbot_dialog.exec()

    def unlike_cat(self):
        self.show_status_message("Fonctionnalité 'Dé-liker' complète non implémentée.", "orange")
        self.set_like_button_state(False)

    def save_cat_image(self):
        if not self.requests_module:
            self.show_status_message("Erreur: Le module 'requests' n'est pas disponible pour l'enregistrement.", "red")
            return
        if not self.current_cat_image_url:
            self.show_status_message("Aucune image à enregistrer.", "red")
            return

        if not os.path.exists(FAVORITES_FOLDER):
            os.makedirs(FAVORITES_FOLDER)

        try:
            image_data = self.requests_module.get(self.current_cat_image_url).content
            
            base_name = "chat"
            if self.current_cat_breed_name and self.current_cat_breed_name != 'Race inconnue':
                base_name = "".join(c for c in self.current_cat_breed_name if c.isalnum() or c.isspace()).strip()
                base_name = base_name.replace(" ", "_")
                if not base_name:
                    base_name = "chat"
            
            random_digits = f"{random.randint(0, 99):02d}"
            
            file_extension = os.path.splitext(self.current_cat_image_url)[1]
            if not file_extension:
                file_extension = ".jpg"
            
            filename = f"{base_name}_{random_digits}{file_extension}"
            filepath = os.path.join(FAVORITES_FOLDER, filename)

            counter = 1
            original_filepath = filepath
            while os.path.exists(filepath):
                name_without_ext, ext = os.path.splitext(original_filepath)
                if f"_{random_digits}" in name_without_ext:
                    parts = name_without_ext.split('_')
                    if parts[-1].isdigit() and len(parts[-1]) < 4:
                        name_without_random_and_counter = '_'.join(parts[:-1])
                        filepath = f"{name_without_random_and_counter}_{random_digits}_{counter}{ext}"
                    else:
                        filepath = f"{name_without_ext}_{counter}{ext}"
                else:
                    filepath = f"{name_without_ext}_{counter}{ext}"
                
                counter += 1


            with open(filepath, 'wb') as f:
                f.write(image_data)
            self.show_status_message(f"Image enregistrée sous '{os.path.basename(filepath)}' !", "green")
            self.save_button.setEnabled(False)
            self.save_button.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))

        except self.requests_module.exceptions.RequestException as e:
            self.show_status_message(f"Erreur réseau lors de l'enregistrement: {e}", "red")
        except Exception as e:
            self.show_status_message(f"Erreur lors de l'enregistrement de l'image: {e}", "red")

    def show_status_message(self, message: str, color: str = "white", duration_ms: int = 3000):
        self.status_message_label.setText(message)
        self.status_message_label.setStyleSheet(f"QLabel#statusMessage {{ color: {color}; }}")
        self.status_message_timer.start(duration_ms)


if __name__ == "__main__":
    try:
        from PIL import Image, ImageDraw, ImageFont

        def create_heart_icon(filename, fill_color, outline_color):
            if not os.path.exists(filename):
                img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                points = [
                    (25, 10), (30, 0), (45, 5), (45, 15), (25, 45), (5, 15), (5, 5), (20, 0)
                ]
                d.polygon(points, fill=fill_color, outline=outline_color)
                img.save(filename)

        create_heart_icon("heart-outline.png", (0, 0, 0, 0), (255, 255, 255))
        create_heart_icon("heart-filled.png", (224, 74, 90), (224, 74, 90))
        print("Icônes de cœur factices créées.")
    except ImportError:
        print("Pillow n'est pas installé. Impossible de créer les icônes de cœur. Les boutons afficheront des caractères textuels.")


    if not os.path.exists("loading_cat.gif"):
        print("Création d'un 'loading_cat.gif' factice.")
        try:
            from PIL import Image, ImageDraw, ImageFont
            images = []
            width, height = 120, 120
            purple_color = (187, 134, 252)
            bg_color = (44, 44, 44)
            text_color = (204, 204, 204)

            for i in range(20):
                img = Image.new('RGB', (width, height), color=bg_color)
                d = ImageDraw.Draw(img)
                angle = i * (360 / 20)
                square_size = 30
                center_x, center_y = width // 2, height // 2
                half_size = square_size // 2

                corners = [
                    (-half_size, -half_size), (half_size, -half_size),
                    (half_size, half_size), (-half_size, half_size)
                ]

                rotated_corners = []
                rad_angle = math.radians(angle)
                for x, y in corners:
                    rotated_x = x * math.cos(rad_angle) - y * math.sin(rad_angle)
                    rotated_y = x * math.sin(rad_angle) + y * math.cos(rad_angle)
                    rotated_corners.append((rotated_x + center_x, rotated_y + center_y))

                d.polygon(rotated_corners, fill=purple_color)

                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except IOError:
                    font = ImageFont.load_default()

                text_width = d.textlength("Loading...", font=font)
                d.text(((width - text_width) / 2, height - 25), "Chargement...", fill=text_color, font=font)
                images.append(img)
            images[0].save("loading_cat.gif", save_all=True, append_images=images[1:], optimize=False, duration=80, loop=0)
        except ImportError:
            print("Pillow n'est pas installé. Impossible de créer un GIF factice. L'écran de chargement affichera le texte 'Chargement...'.")


    app = QApplication(sys.argv)
    loading_screen = LoadingScreen()
    loading_screen.show()
    sys.exit(app.exec())