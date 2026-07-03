# GUI kütüphanesi ve bileşenleri
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
# Veritabanı, dosya işlemleri ve CSV için
import sqlite3, os, shutil, csv, traceback
# Resim işleme
from PIL import Image, ImageTk
from datetime import datetime, date
# Merkezi yapılandırma
from config import (DB_YOLU, RESIM_DIZINI, DURUMLAR, DURUM_RENKLERI,
                    RENKLER, SATIR_RENKLERI, KISAYOLLAR)

# ── Veritabanı yardımcıları ────────────────────────────────────────────────

def db_baglan():
    """Context manager olmadan kullanım için bağlantı döndürür."""
    return sqlite3.connect(DB_YOLU)


def veritabani_hazirla():
    if not os.path.exists(RESIM_DIZINI):
        os.makedirs(RESIM_DIZINI)
    try:
        with sqlite3.connect(DB_YOLU) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS esyalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aciklama TEXT,
                konum TEXT,
                teslim_edilen TEXT,
                foto_yolu TEXT,
                durum TEXT DEFAULT 'Bulundu',
                notlar TEXT DEFAULT '',
                eklenme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            # İşlem logu tablosu
            c.execute('''CREATE TABLE IF NOT EXISTS islem_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                esya_id INTEGER,
                islem TEXT,
                detay TEXT,
                tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            # Eski DB'lerde eksik sütunları ekle
            for sutun, tanim in [("notlar", "TEXT DEFAULT ''"),
                                  ("eklenme_tarihi", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")]:
                try:
                    c.execute(f"ALTER TABLE esyalar ADD COLUMN {sutun} {tanim}")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
    except sqlite3.Error as e:
        messagebox.showerror("Veritabanı Hatası", f"Veritabanı hazırlanamadı:\n{e}")
        raise


def log_ekle(conn, esya_id, islem, detay=""):
    """İşlem loguna satır ekler; mevcut bağlantıyı kullanır."""
    try:
        conn.execute(
            "INSERT INTO islem_log (esya_id, islem, detay) VALUES (?,?,?)",
            (esya_id, islem, detay))
    except sqlite3.Error:
        pass  # Log hatası uygulamayı durdurmasın


# ── Toast bildirimi ────────────────────────────────────────────────────────

class Toast:
    """Ekranın sağ altında kısa süre görünen bildirim penceresi."""

    def __init__(self, root, mesaj, tur="bilgi", sure=2500):
        self.root = root
        t = _aktif_tema()
        renk_map = {"bilgi": t["accent"], "basari": t["success"],
                    "hata": t["danger"], "uyari": t["warning"]}
        bg = renk_map.get(tur, t["accent"])

        self.pencere = tk.Toplevel(root)
        self.pencere.overrideredirect(True)   # Başlık çubuğu yok
        self.pencere.attributes("-topmost", True)
        self.pencere.configure(bg=bg)

        tk.Label(self.pencere, text=mesaj, bg=bg, fg="#FFFFFF",
                 font=("Segoe UI", 10), padx=16, pady=10).pack()

        self._konumlandir()
        self.pencere.after(sure, self._kapat)

    def _konumlandir(self):
        self.root.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()
        ry = self.root.winfo_y() + self.root.winfo_height()
        self.pencere.update_idletasks()
        w = self.pencere.winfo_width()
        h = self.pencere.winfo_height()
        self.pencere.geometry(f"+{rx - w - 20}+{ry - h - 40}")

    def _kapat(self):
        try:
            self.pencere.destroy()
        except tk.TclError:
            pass


# Tema erişimi için global referans (Toast içinde kullanılır)
_tema_ref = {"tema": RENKLER["light"]}

def _aktif_tema():
    return _tema_ref["tema"]


# ── Placeholder'lı giriş alanı ────────────────────────────────────────────

class PlaceholderEntry(tk.Entry):
    def __init__(self, parent, placeholder, tema, **kwargs):
        super().__init__(parent, **kwargs)
        self.placeholder = placeholder
        self.tema = tema
        self._aktif = False
        self.bind("<FocusIn>",  self._giris)
        self.bind("<FocusOut>", self._cikis)
        self._goster()

    def _goster(self):
        self.delete(0, tk.END)
        self.insert(0, self.placeholder)
        self.config(fg=self.tema["subtext"])
        self._aktif = True

    def _giris(self, _):
        if self._aktif:
            self.delete(0, tk.END)
            self.config(fg=self.tema["text"])
            self._aktif = False

    def _cikis(self, _):
        if not self.get():
            self._goster()

    def deger_al(self):
        return "" if self._aktif else self.get()

    def temizle(self):
        self._goster()

    def tema_guncelle(self, tema):
        self.tema = tema
        self.config(fg=tema["subtext"] if self._aktif else tema["text"])


# ── Ana uygulama ───────────────────────────────────────────────────────────

class ProfoundApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ProFound — Kayıp Eşya Takip Sistemi")
        self.root.geometry("1150x740")
        self.root.minsize(900, 600)

        veritabani_hazirla()

        self.aktif_tema_adi = "light"
        self.tema = RENKLER["light"]
        _tema_ref["tema"] = self.tema

        self.secili_resim_yolu = ""
        self.durum_filtresi    = tk.StringVar(value="Tümü")
        self.duzenleme_modu    = False
        self.duzenlenen_id     = None
        self.form_cerceve      = None

        # Tarih filtresi değişkenleri
        self.tarih_baslangic = tk.StringVar(value="")
        self.tarih_bitis     = tk.StringVar(value="")

        self.treeview_style = ttk.Style()
        self._stil_ayarla()
        self.arayuz_olustur()
        self._kisayollari_bagla()
        self.listele()

    # ── Klavye kısayolları ─────────────────────────────────────────────────

    def _kisayollari_bagla(self):
        eylemler = {
            "yeni_kayit":     self.form_ac,
            "secili_sil":     self.secili_sil,
            "yenile":         self.listele,
            "aramaya_odaklan": lambda *_: self.ent_ara.focus_set(),
            "formu_kapat":    self._formu_kapat,
        }
        for tus, eylem_adi in KISAYOLLAR.items():
            eylem = eylemler.get(eylem_adi)
            if eylem:
                self.root.bind(tus, lambda e, f=eylem: f())

    def _formu_kapat(self):
        if self.form_cerceve and self.form_cerceve.winfo_exists():
            self.form_cerceve.destroy()

    # ── Stil ──────────────────────────────────────────────────────────────

    def _stil_ayarla(self):
        t = self.tema
        self.treeview_style.theme_use("clam")
        self.treeview_style.configure(
            "Custom.Treeview",
            background=t["row_odd"], fieldbackground=t["row_odd"],
            foreground=t["text"], rowheight=34,
            font=("Segoe UI", 10), borderwidth=0)
        self.treeview_style.configure(
            "Custom.Treeview.Heading",
            background=t["header_bg"], foreground=t["header_fg"],
            font=("Segoe UI", 10, "bold"), relief="flat")
        self.treeview_style.map(
            "Custom.Treeview",
            background=[("selected", t["accent"])],
            foreground=[("selected", "#FFFFFF")])

    # ── Arayüz ────────────────────────────────────────────────────────────

    def arayuz_olustur(self):
        t = self.tema
        self.root.configure(bg=t["bg"])

        # Sidebar
        self.sidebar = tk.Frame(self.root, bg=t["sidebar"], width=225)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo_f = tk.Frame(self.sidebar, bg=t["sidebar"], pady=20)
        logo_f.pack(fill="x")
        tk.Label(logo_f, text="🔍", bg=t["sidebar"], font=("Segoe UI", 28)).pack()
        tk.Label(logo_f, text="ProFound", bg=t["sidebar"], fg=t["sidebar_text"],
                 font=("Segoe UI", 16, "bold")).pack()
        tk.Label(logo_f, text="Eşya Takip Sistemi", bg=t["sidebar"], fg=t["subtext"],
                 font=("Segoe UI", 9)).pack()

        ttk.Separator(self.sidebar).pack(fill="x", padx=15, pady=5)

        menu_items = [
            ("📋  Tüm Kayıtlar",    "Tümü"),
            ("🟢  Bulunan",         "Bulundu"),
            ("🟡  Teslim Bekleyen", "Teslim Bekliyor"),
            ("🔵  Teslim Edilen",   "Teslim Edildi"),
            ("🔴  Kayıp",           "Kayıp"),
        ]
        self.sidebar_butonlar = []
        for metin, filtre in menu_items:
            btn = tk.Button(
                self.sidebar, text=metin, bg=t["sidebar"], fg=t["sidebar_text"],
                font=("Segoe UI", 10), bd=0, pady=10, anchor="w", padx=20,
                activebackground=t["sidebar_hover"], cursor="hand2",
                command=lambda f=filtre: (self.durum_filtresi.set(f), self.listele()))
            btn.pack(fill="x")
            self.sidebar_butonlar.append(btn)

        ttk.Separator(self.sidebar).pack(fill="x", padx=15, pady=10)

        self.btn_tema = tk.Button(
            self.sidebar,
            text="🌙  Koyu Mod" if self.aktif_tema_adi == "light" else "☀️  Açık Mod",
            bg=t["sidebar"], fg=t["sidebar_text"], font=("Segoe UI", 10),
            bd=0, pady=10, anchor="w", padx=20,
            activebackground=t["sidebar_hover"], cursor="hand2",
            command=self.tema_degistir)
        self.btn_tema.pack(fill="x")

        tk.Button(self.sidebar, text="📤  CSV Dışa Aktar", bg=t["sidebar"],
                  fg=t["sidebar_text"], font=("Segoe UI", 10), bd=0, pady=10,
                  anchor="w", padx=20, activebackground=t["sidebar_hover"],
                  cursor="hand2", command=self.disari_aktar).pack(fill="x")

        tk.Button(self.sidebar, text="📥  CSV İçe Aktar", bg=t["sidebar"],
                  fg=t["sidebar_text"], font=("Segoe UI", 10), bd=0, pady=10,
                  anchor="w", padx=20, activebackground=t["sidebar_hover"],
                  cursor="hand2", command=self.iceri_aktar).pack(fill="x")

        tk.Button(self.sidebar, text="📜  İşlem Logu", bg=t["sidebar"],
                  fg=t["sidebar_text"], font=("Segoe UI", 10), bd=0, pady=10,
                  anchor="w", padx=20, activebackground=t["sidebar_hover"],
                  cursor="hand2", command=self.log_goster).pack(fill="x")

        # İstatistik
        self.stat_frame = tk.Frame(self.sidebar, bg=t["sidebar"], pady=20)
        self.stat_frame.pack(side="bottom", fill="x")
        self.lbl_stat = tk.Label(self.stat_frame, text="", bg=t["sidebar"],
                                 fg=t["subtext"], font=("Segoe UI", 9),
                                 justify="left", padx=20)
        self.lbl_stat.pack(anchor="w")

        # Ana içerik
        self.main_frame = tk.Frame(self.root, bg=t["bg"])
        self.main_frame.pack(side="left", fill="both", expand=True)

        # Üst çubuk
        self.topbar = tk.Frame(self.main_frame, bg=t["panel"], pady=12, padx=20)
        self.topbar.pack(fill="x")
        tk.Label(self.topbar, text="Kayıtlar", bg=t["panel"], fg=t["text"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        # Kısayol ipucu
        tk.Label(self.topbar, text="Ctrl+N: Yeni  |  F5: Yenile  |  Ctrl+F: Ara",
                 bg=t["panel"], fg=t["subtext"], font=("Segoe UI", 8)).pack(side="left", padx=20)

        self.btn_yeni = tk.Button(
            self.topbar, text="＋  Yeni Kayıt", bg=t["accent"], fg="white",
            font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=6, cursor="hand2",
            command=self.form_ac)
        self.btn_yeni.pack(side="right")

        # Arama çubuğu
        search_bar = tk.Frame(self.main_frame, bg=t["bg"], pady=8, padx=20)
        search_bar.pack(fill="x")
        search_inner = tk.Frame(search_bar, bg=t["panel"], bd=0,
                                highlightthickness=1, highlightbackground=t["border"])
        search_inner.pack(side="left", fill="x", expand=True)
        tk.Label(search_inner, text="🔍", bg=t["panel"], fg=t["subtext"],
                 font=("Segoe UI", 11)).pack(side="left", padx=8)
        self.ent_ara = tk.Entry(search_inner, font=("Segoe UI", 11), bg=t["panel"],
                                fg=t["text"], bd=0, insertbackground=t["text"])
        self.ent_ara.pack(side="left", fill="x", expand=True, ipady=8)
        self.ent_ara.bind("<KeyRelease>", lambda e: self.listele())

        # Tarih filtresi
        tarih_f = tk.Frame(self.main_frame, bg=t["bg"], padx=20, pady=2)
        tarih_f.pack(fill="x")
        tk.Label(tarih_f, text="Tarih aralığı:", bg=t["bg"], fg=t["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")

        self.ent_baslangic = tk.Entry(tarih_f, textvariable=self.tarih_baslangic,
                                      width=12, font=("Segoe UI", 9), bg=t["input_bg"],
                                      fg=t["text"], bd=0, insertbackground=t["text"],
                                      highlightthickness=1, highlightbackground=t["border"])
        self.ent_baslangic.pack(side="left", padx=(6, 2), ipady=4)
        tk.Label(tarih_f, text="GG.AA.YYYY", bg=t["bg"], fg=t["subtext"],
                 font=("Segoe UI", 8)).pack(side="left")

        tk.Label(tarih_f, text=" — ", bg=t["bg"], fg=t["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")

        self.ent_bitis = tk.Entry(tarih_f, textvariable=self.tarih_bitis,
                                  width=12, font=("Segoe UI", 9), bg=t["input_bg"],
                                  fg=t["text"], bd=0, insertbackground=t["text"],
                                  highlightthickness=1, highlightbackground=t["border"])
        self.ent_bitis.pack(side="left", padx=(2, 2), ipady=4)
        tk.Label(tarih_f, text="GG.AA.YYYY", bg=t["bg"], fg=t["subtext"],
                 font=("Segoe UI", 8)).pack(side="left")

        tk.Button(tarih_f, text="Uygula", bg=t["accent"], fg="white",
                  font=("Segoe UI", 9), bd=0, padx=10, pady=3, cursor="hand2",
                  command=self.listele).pack(side="left", padx=8)
        tk.Button(tarih_f, text="Temizle", bg=t["subtext"], fg="white",
                  font=("Segoe UI", 9), bd=0, padx=10, pady=3, cursor="hand2",
                  command=self._tarih_temizle).pack(side="left")

        # Tablo
        list_frame = tk.Frame(self.main_frame, bg=t["bg"], padx=20)
        list_frame.pack(fill="both", expand=True, pady=(6, 10))

        cols = ("ID", "Açıklama", "Konum", "Teslim/Konum", "Durum", "Tarih")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                  style="Custom.Treeview", selectmode="browse")
        genislikler = [50, 220, 160, 160, 120, 130]
        for col, w in zip(cols, genislikler):
            self.tree.heading(col, text=col,
                              command=lambda c=col: self._sutuna_gore_sirala(c))
            self.tree.column(col, width=w,
                             anchor="center" if col in ("ID","Durum","Tarih") else "w")

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for durum, renk in SATIR_RENKLERI.items():
            self.tree.tag_configure(durum, background=renk)

        self.tree.bind("<Double-1>", self.detay_goster)
        self.tree.bind("<Delete>",   self.secili_sil)
        self.tree.bind("<Button-1>", self._bosluk_tikla)

        # Sıralama durumu
        self._siralama = {"sutun": None, "ters": False}

    # ── Yardımcı ──────────────────────────────────────────────────────────

    def _bosluk_tikla(self, event):
        if not self.tree.identify_row(event.y):
            self.tree.selection_remove(self.tree.selection())

    def _tarih_temizle(self):
        self.tarih_baslangic.set("")
        self.tarih_bitis.set("")
        self.listele()

    def _tarih_parse(self, metin):
        """GG.AA.YYYY → date nesnesi; başarısız olursa None."""
        try:
            return datetime.strptime(metin.strip(), "%d.%m.%Y").date()
        except ValueError:
            return None

    def _sutuna_gore_sirala(self, sutun):
        """Sütun başlığına tıklayınca tablo sıralanır."""
        if self._siralama["sutun"] == sutun:
            self._siralama["ters"] = not self._siralama["ters"]
        else:
            self._siralama["sutun"] = sutun
            self._siralama["ters"] = False

        satirlar = [(self.tree.set(k, sutun), k) for k in self.tree.get_children("")]
        try:
            satirlar.sort(key=lambda x: int(x[0]) if x[0].isdigit() else x[0].lower(),
                          reverse=self._siralama["ters"])
        except Exception:
            satirlar.sort(reverse=self._siralama["ters"])

        for idx, (_, k) in enumerate(satirlar):
            self.tree.move(k, "", idx)

    def toast(self, mesaj, tur="bilgi"):
        Toast(self.root, mesaj, tur)

    # ── Form ──────────────────────────────────────────────────────────────

    def form_ac(self, duzenleme=False, veri=None):
        if self.form_cerceve and self.form_cerceve.winfo_exists():
            self.form_cerceve.destroy()

        t = self.tema
        self.duzenleme_modu = duzenleme
        self.duzenlenen_id  = veri[0] if veri else None

        pencere = tk.Toplevel(self.root)
        pencere.title("Eşya Düzenle" if duzenleme else "Yeni Eşya Ekle")
        pencere.geometry("500x590")
        pencere.configure(bg=t["panel"])
        pencere.resizable(False, False)
        pencere.grab_set()
        self.form_cerceve = pencere

        # Escape ile kapat
        pencere.bind("<Escape>", lambda _: pencere.destroy())

        baslik = "✏️  Kaydı Düzenle" if duzenleme else "➕  Yeni Eşya Ekle"
        tk.Label(pencere, text=baslik, bg=t["panel"], fg=t["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 5), padx=25, anchor="w")
        ttk.Separator(pencere).pack(fill="x", padx=25, pady=5)

        ic = tk.Frame(pencere, bg=t["panel"], padx=25)
        ic.pack(fill="x")

        def etiket(text):
            tk.Label(ic, text=text, bg=t["panel"], fg=t["subtext"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))

        def giris(placeholder):
            e = PlaceholderEntry(ic, placeholder, t, font=("Segoe UI", 11),
                                 bg=t["input_bg"], fg=t["text"], bd=0,
                                 highlightthickness=1, highlightbackground=t["border"],
                                 insertbackground=t["text"])
            e.pack(fill="x", ipady=7)
            return e

        etiket("EŞYA AÇIKLAMASI *")
        self.f_aciklama = giris("örn. Mavi çanta, cüzdan, kulaklık...")
        etiket("NEREDE BULUNDU?")
        self.f_konum = giris("örn. A Blok 3. Kat, Yemekhane girişi...")
        etiket("ŞU AN NEREDE / KİMDE?")
        self.f_teslim = giris("örn. Güvenlik ofisi, 301 nolu oda...")

        etiket("NOTLAR")
        self.f_notlar = tk.Text(ic, font=("Segoe UI", 10), bg=t["input_bg"],
                                 fg=t["text"], bd=0, highlightthickness=1,
                                 highlightbackground=t["border"], height=3,
                                 wrap="word", insertbackground=t["text"])
        self.f_notlar.pack(fill="x")

        etiket("DURUM")
        self.f_durum = ttk.Combobox(ic, values=DURUMLAR, state="readonly",
                                     font=("Segoe UI", 10))
        self.f_durum.set("Bulundu")
        self.f_durum.pack(fill="x", ipady=5)

        foto_frame = tk.Frame(ic, bg=t["panel"])
        foto_frame.pack(fill="x", pady=(12, 0))
        self.lbl_onizleme = tk.Label(foto_frame, text="📷\nFotoğraf Seç",
                                      bg=t["input_bg"], fg=t["subtext"],
                                      width=12, height=5, cursor="hand2",
                                      relief="flat", bd=0,
                                      highlightthickness=1, highlightbackground=t["border"],
                                      font=("Segoe UI", 9))
        self.lbl_onizleme.pack(side="left")
        self.lbl_onizleme.bind("<Button-1>", lambda e: self.resim_sec())
        self.secili_resim_yolu = ""

        if duzenleme and veri:
            self._form_doldur(veri)

        tk.Button(pencere, text="KAYDET", bg=t["accent"], fg="white",
                  font=("Segoe UI", 11, "bold"), bd=0, pady=10, cursor="hand2",
                  command=self.kaydet).pack(fill="x", padx=25, pady=15)

    def _form_doldur(self, veri):
        for entry, deger in [(self.f_aciklama, veri[1]),
                              (self.f_konum,    veri[2]),
                              (self.f_teslim,   veri[3])]:
            if deger:
                entry.delete(0, tk.END)
                entry.insert(0, deger)
                entry.config(fg=self.tema["text"])
                entry._aktif = False
        if veri[6]:
            self.f_notlar.insert("1.0", veri[6])
        self.f_durum.set(veri[5] if veri[5] else "Bulundu")
        if veri[4] and os.path.exists(veri[4]):
            self.secili_resim_yolu = veri[4]
            self._onizleme_goster(veri[4])

    def _onizleme_goster(self, yol):
        try:
            img = Image.open(yol).resize((90, 80))
            self.img_tk = ImageTk.PhotoImage(img)
            self.lbl_onizleme.config(image=self.img_tk, text="")
        except Exception as e:
            self.toast(f"Resim açılamadı: {e}", "hata")

    def resim_sec(self):
        dosya = filedialog.askopenfilename(
            filetypes=[("Resim", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if dosya:
            self.secili_resim_yolu = dosya
            self._onizleme_goster(dosya)

    def kaydet(self):
        aciklama = self.f_aciklama.deger_al()
        if not aciklama:
            self.toast("Lütfen bir açıklama girin!", "uyari")
            return

        konum  = self.f_konum.deger_al()
        teslim = self.f_teslim.deger_al()
        notlar = self.f_notlar.get("1.0", tk.END).strip()
        durum  = self.f_durum.get()

        final_yol = ""
        if self.secili_resim_yolu and self.secili_resim_yolu != self._mevcut_foto():
            try:
                dosya_adi = os.path.basename(self.secili_resim_yolu)
                final_yol = os.path.join(RESIM_DIZINI, f"{os.urandom(4).hex()}_{dosya_adi}")
                shutil.copy2(self.secili_resim_yolu, final_yol)
            except OSError as e:
                self.toast(f"Resim kopyalanamadı: {e}", "hata")
                return
        elif self.secili_resim_yolu:
            final_yol = self.secili_resim_yolu

        try:
            with sqlite3.connect(DB_YOLU) as conn:
                c = conn.cursor()
                if self.duzenleme_modu and self.duzenlenen_id:
                    c.execute(
                        "UPDATE esyalar SET aciklama=?, konum=?, teslim_edilen=?, "
                        "foto_yolu=?, durum=?, notlar=? WHERE id=?",
                        (aciklama, konum, teslim, final_yol, durum, notlar, self.duzenlenen_id))
                    log_ekle(conn, self.duzenlenen_id, "GÜNCELLEME",
                             f"Durum: {durum} | Açıklama: {aciklama}")
                    self.toast("Kayıt güncellendi.", "basari")
                else:
                    c.execute(
                        "INSERT INTO esyalar (aciklama, konum, teslim_edilen, foto_yolu, durum, notlar) "
                        "VALUES (?,?,?,?,?,?)",
                        (aciklama, konum, teslim, final_yol, durum, notlar))
                    yeni_id = c.lastrowid
                    log_ekle(conn, yeni_id, "EKLEME", f"Açıklama: {aciklama}")
                    self.toast("Yeni kayıt eklendi.", "basari")
                conn.commit()
        except sqlite3.Error as e:
            self.toast(f"Kayıt başarısız: {e}", "hata")
            return

        self.form_cerceve.destroy()
        self.listele()
        self.istatistik_guncelle()

    def _mevcut_foto(self):
        if self.duzenleme_modu and self.duzenlenen_id:
            try:
                with sqlite3.connect(DB_YOLU) as conn:
                    r = conn.execute("SELECT foto_yolu FROM esyalar WHERE id=?",
                                     (self.duzenlenen_id,)).fetchone()
                return r[0] if r else ""
            except sqlite3.Error:
                return ""
        return ""

    # ── Listeleme ─────────────────────────────────────────────────────────

    def listele(self, *_):
        for i in self.tree.get_children():
            self.tree.delete(i)

        kelime = self.ent_ara.get()
        filtre = self.durum_filtresi.get()
        bas    = self._tarih_parse(self.tarih_baslangic.get())
        bit    = self._tarih_parse(self.tarih_bitis.get())

        sorgu = """SELECT id, aciklama, konum, teslim_edilen, durum,
                   strftime('%d.%m.%Y', eklenme_tarihi) as tarih,
                   eklenme_tarihi
                   FROM esyalar
                   WHERE (aciklama LIKE ? OR konum LIKE ? OR teslim_edilen LIKE ?)"""
        params = [f"%{kelime}%"] * 3

        if filtre != "Tümü":
            sorgu += " AND durum=?"
            params.append(filtre)

        # Tarih filtresi — SQLite'ta ISO format karşılaştırması çalışır
        if bas:
            sorgu += " AND date(eklenme_tarihi) >= ?"
            params.append(bas.isoformat())
        if bit:
            sorgu += " AND date(eklenme_tarihi) <= ?"
            params.append(bit.isoformat())

        sorgu += " ORDER BY eklenme_tarihi DESC"

        try:
            with sqlite3.connect(DB_YOLU) as conn:
                satirlar = conn.execute(sorgu, params).fetchall()
        except sqlite3.Error as e:
            self.toast(f"Listeleme hatası: {e}", "hata")
            return

        for satir in satirlar:
            esya_id = satir[0]
            durum   = satir[4] or "Bulundu"
            # iid olarak veritabanı ID'sini kullan → id_haritası gerekmez
            self.tree.insert("", tk.END, iid=str(esya_id),
                             values=(satir[0], satir[1], satir[2], satir[3], durum, satir[5]),
                             tags=(durum,))

        self.istatistik_guncelle()

    def _secili_id(self):
        """Seçili satırın veritabanı ID'sini döndürür (iid üzerinden)."""
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def istatistik_guncelle(self):
        try:
            with sqlite3.connect(DB_YOLU) as conn:
                sayilar = dict(conn.execute(
                    "SELECT durum, COUNT(*) FROM esyalar GROUP BY durum").fetchall())
        except sqlite3.Error:
            return
        toplam = sum(sayilar.values())
        satirlar = [f"Toplam: {toplam} kayıt"]
        for durum, emoji in [("Bulundu","🟢"), ("Teslim Bekliyor","🟡"),
                              ("Teslim Edildi","🔵"), ("Kayıp","🔴")]:
            satirlar.append(f"{emoji} {durum}: {sayilar.get(durum, 0)}")
        self.lbl_stat.config(text="\n".join(satirlar))

    # ── Detay penceresi ───────────────────────────────────────────────────

    def detay_goster(self, event=None):
        esya_id = self._secili_id()
        if esya_id is None:
            return
        try:
            with sqlite3.connect(DB_YOLU) as conn:
                veri = conn.execute("SELECT * FROM esyalar WHERE id=?",
                                    (esya_id,)).fetchone()
        except sqlite3.Error as e:
            self.toast(f"Detay alınamadı: {e}", "hata")
            return
        if veri:
            DetayPenceresi(self.root, veri, self.listele, self.tema,
                           self.form_ac, self.toast)

    # ── Silme ─────────────────────────────────────────────────────────────

    def secili_sil(self, *_):
        esya_id = self._secili_id()
        if esya_id is None:
            return
        if not messagebox.askyesno("Sil", "Bu kaydı silmek istiyor musunuz?"):
            return
        try:
            with sqlite3.connect(DB_YOLU) as conn:
                r = conn.execute("SELECT foto_yolu, aciklama FROM esyalar WHERE id=?",
                                 (esya_id,)).fetchone()
                if r:
                    if r[0] and os.path.exists(r[0]):
                        os.remove(r[0])
                    log_ekle(conn, esya_id, "SİLME", f"Açıklama: {r[1]}")
                conn.execute("DELETE FROM esyalar WHERE id=?", (esya_id,))
                conn.commit()
            self.toast("Kayıt silindi.", "basari")
        except (sqlite3.Error, OSError) as e:
            self.toast(f"Silme hatası: {e}", "hata")
        self.listele()

    # ── CSV dışa/içe aktarma ──────────────────────────────────────────────

    def disari_aktar(self):
        dosya = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="envanter.csv")
        if not dosya:
            return
        try:
            with sqlite3.connect(DB_YOLU) as conn:
                veriler = conn.execute(
                    "SELECT id, aciklama, konum, teslim_edilen, durum, notlar, eklenme_tarihi "
                    "FROM esyalar").fetchall()
            with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["ID", "Açıklama", "Konum", "Teslim/Konum",
                             "Durum", "Notlar", "Tarih"])
                w.writerows(veriler)
            self.toast(f"CSV oluşturuldu: {os.path.basename(dosya)}", "basari")
        except (sqlite3.Error, OSError) as e:
            self.toast(f"Dışa aktarma hatası: {e}", "hata")

    def iceri_aktar(self):
        """CSV dosyasından kayıt içe aktarır. Başlık satırını atlar."""
        dosya = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not dosya:
            return
        eklenen = 0
        hatali  = 0
        try:
            with open(dosya, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                with sqlite3.connect(DB_YOLU) as conn:
                    for satir in reader:
                        try:
                            aciklama = satir.get("Açıklama", "").strip()
                            if not aciklama:
                                hatali += 1
                                continue
                            konum  = satir.get("Konum", "").strip()
                            teslim = satir.get("Teslim/Konum", "").strip()
                            durum  = satir.get("Durum", "Bulundu").strip()
                            notlar = satir.get("Notlar", "").strip()
                            if durum not in DURUMLAR:
                                durum = "Bulundu"
                            c = conn.execute(
                                "INSERT INTO esyalar (aciklama, konum, teslim_edilen, durum, notlar) "
                                "VALUES (?,?,?,?,?)",
                                (aciklama, konum, teslim, durum, notlar))
                            log_ekle(conn, c.lastrowid, "CSV İÇE AKTARMA",
                                     f"Açıklama: {aciklama}")
                            eklenen += 1
                        except sqlite3.Error:
                            hatali += 1
                    conn.commit()
        except (OSError, csv.Error) as e:
            self.toast(f"İçe aktarma hatası: {e}", "hata")
            return

        self.listele()
        self.toast(f"{eklenen} kayıt eklendi, {hatali} satır atlandı.",
                   "basari" if eklenen > 0 else "uyari")

    # ── İşlem logu penceresi ──────────────────────────────────────────────

    def log_goster(self):
        t = self.tema
        pencere = tk.Toplevel(self.root)
        pencere.title("İşlem Geçmişi")
        pencere.geometry("680x460")
        pencere.configure(bg=t["bg"])
        pencere.grab_set()

        tk.Label(pencere, text="📜  İşlem Geçmişi", bg=t["bg"], fg=t["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(16, 4), padx=20, anchor="w")
        ttk.Separator(pencere).pack(fill="x", padx=20, pady=4)

        cols = ("Tarih", "Eşya ID", "İşlem", "Detay")
        tree = ttk.Treeview(pencere, columns=cols, show="headings",
                             style="Custom.Treeview")
        for col, w in zip(cols, [140, 70, 120, 320]):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(pencere, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)

        f = tk.Frame(pencere, bg=t["bg"])
        f.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        tree.pack(in_=f, side="left", fill="both", expand=True)
        sb.pack(in_=f, side="right", fill="y")

        try:
            with sqlite3.connect(DB_YOLU) as conn:
                kayitlar = conn.execute(
                    "SELECT strftime('%d.%m.%Y %H:%M', tarih), esya_id, islem, detay "
                    "FROM islem_log ORDER BY tarih DESC LIMIT 500").fetchall()
        except sqlite3.Error as e:
            self.toast(f"Log alınamadı: {e}", "hata")
            return

        for k in kayitlar:
            tree.insert("", tk.END, values=k)

        if not kayitlar:
            tk.Label(pencere, text="Henüz işlem kaydı yok.",
                     bg=t["bg"], fg=t["subtext"], font=("Segoe UI", 10)).pack()

    # ── Tema ──────────────────────────────────────────────────────────────

    def tema_degistir(self):
        # Mevcut arama metnini ve filtreyi koru
        mevcut_ara    = self.ent_ara.get()
        mevcut_filtre = self.durum_filtresi.get()
        mevcut_bas    = self.tarih_baslangic.get()
        mevcut_bit    = self.tarih_bitis.get()

        self.aktif_tema_adi = "dark" if self.aktif_tema_adi == "light" else "light"
        self.tema = RENKLER[self.aktif_tema_adi]
        _tema_ref["tema"] = self.tema

        for widget in self.root.winfo_children():
            widget.destroy()

        self._stil_ayarla()
        self.arayuz_olustur()
        self._kisayollari_bagla()

        # Durumu geri yükle
        self.durum_filtresi.set(mevcut_filtre)
        self.tarih_baslangic.set(mevcut_bas)
        self.tarih_bitis.set(mevcut_bit)
        self.ent_ara.delete(0, tk.END)
        if mevcut_ara:
            self.ent_ara.insert(0, mevcut_ara)

        self.btn_tema.config(
            text="☀️  Açık Mod" if self.aktif_tema_adi == "dark" else "🌙  Koyu Mod")
        self.listele()


# ── Detay penceresi ────────────────────────────────────────────────────────

class DetayPenceresi(tk.Toplevel):
    def __init__(self, parent, veri, yenile_fonk, tema, form_ac_fonk, toast_fonk):
        super().__init__(parent)
        self.veri        = veri
        self.yenile_fonk = yenile_fonk
        self.tema        = tema
        self.form_ac_fonk = form_ac_fonk
        self.toast_fonk  = toast_fonk

        t = tema
        self.title(f"Eşya Detayı — #{veri[0]}")
        self.geometry("480x620")
        self.configure(bg=t["panel"])
        self.resizable(True, True)
        self.grab_set()
        self.bind("<Escape>", lambda _: self.destroy())

        # Başlık şeridi
        baslik_f = tk.Frame(self, bg=t["accent"], pady=15, padx=20)
        baslik_f.pack(fill="x")
        tk.Label(baslik_f, text=veri[1], bg=t["accent"], fg="white",
                 font=("Segoe UI", 13, "bold"), wraplength=400, justify="left").pack(anchor="w")
        durum = veri[5] or "Bulundu"
        renk  = DURUM_RENKLERI.get(durum, t["accent"])
        tk.Label(baslik_f, text=f"● {durum}", bg=t["accent"], fg=renk,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        # Fotoğraf
        foto_f = tk.Frame(self, bg=t["panel"])
        foto_f.pack(fill="x", padx=20, pady=15)
        if veri[4] and os.path.exists(veri[4]):
            try:
                img = Image.open(veri[4]).resize((440, 200))
                self.img_tk = ImageTk.PhotoImage(img)
                tk.Label(foto_f, image=self.img_tk, bg=t["panel"]).pack()
            except Exception:
                tk.Label(foto_f, text="⚠️  Resim açılamadı", bg=t["input_bg"],
                         fg=t["subtext"], pady=20, width=50).pack(fill="x")
        else:
            tk.Label(foto_f, text="📷  Fotoğraf eklenmemiş", bg=t["input_bg"],
                     fg=t["subtext"], font=("Segoe UI", 11), pady=20,
                     width=50).pack(fill="x")

        # Bilgi satırları
        info_f = tk.Frame(self, bg=t["panel"], padx=20)
        info_f.pack(fill="x")
        bilgiler = [
            ("📍 Bulunduğu Yer",  veri[2] or "—"),
            ("📥 Teslim / Konum", veri[3] or "—"),
            ("📅 Kayıt Tarihi",   veri[7] if len(veri) > 7 else "—"),
        ]
        for etiket, deger in bilgiler:
            satir = tk.Frame(info_f, bg=t["panel"], pady=5)
            satir.pack(fill="x")
            tk.Label(satir, text=etiket, bg=t["panel"], fg=t["subtext"],
                     font=("Segoe UI", 9, "bold"), width=18, anchor="w").pack(side="left")
            tk.Label(satir, text=deger, bg=t["panel"], fg=t["text"],
                     font=("Segoe UI", 10), anchor="w").pack(side="left")

        notlar = veri[6] if len(veri) > 6 and veri[6] else ""
        if notlar:
            tk.Label(info_f, text="📝 Notlar", bg=t["panel"], fg=t["subtext"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 3))
            tk.Label(info_f, text=notlar, bg=t["input_bg"], fg=t["text"],
                     font=("Segoe UI", 10), wraplength=420, justify="left",
                     pady=8, padx=10).pack(fill="x")

        # Alt butonlar
        btn_f = tk.Frame(self, bg=t["panel"], pady=15, padx=20)
        btn_f.pack(fill="x", side="bottom")
        tk.Button(btn_f, text="✏️  Düzenle", bg=t["accent"], fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=8,
                  cursor="hand2", command=self._duzenle).pack(side="left", padx=(0, 10))
        tk.Button(btn_f, text="🗑  Sil", bg=t["danger"], fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=8,
                  cursor="hand2", command=self._sil).pack(side="left")

        durum_options = [d for d in DURUM_RENKLERI if d != durum]
        if durum_options:
            self.durum_degistir_var = tk.StringVar(value=durum_options[0])
            tk.OptionMenu(btn_f, self.durum_degistir_var, *durum_options).pack(side="right")
            tk.Button(btn_f, text="Durumu Güncelle", bg=t["warning"], fg="white",
                      font=("Segoe UI", 10), bd=0, padx=10, pady=8,
                      cursor="hand2", command=self._durum_guncelle).pack(side="right", padx=(0,8))

    def _duzenle(self):
        self.destroy()
        self.form_ac_fonk(duzenleme=True, veri=self.veri)

    def _durum_guncelle(self):
        yeni = self.durum_degistir_var.get()
        try:
            with sqlite3.connect(DB_YOLU) as conn:
                conn.execute("UPDATE esyalar SET durum=? WHERE id=?",
                             (yeni, self.veri[0]))
                log_ekle(conn, self.veri[0], "DURUM DEĞİŞİKLİĞİ",
                         f"{self.veri[5]} → {yeni}")
                conn.commit()
            self.toast_fonk(f"Durum güncellendi: {yeni}", "basari")
        except sqlite3.Error as e:
            self.toast_fonk(f"Güncelleme hatası: {e}", "hata")
        self.yenile_fonk()
        self.destroy()

    def _sil(self):
        if not messagebox.askyesno("Sil", "Bu kaydı kalıcı olarak silmek istiyor musunuz?",
                                   parent=self):
            return
        try:
            with sqlite3.connect(DB_YOLU) as conn:
                if self.veri[4] and os.path.exists(self.veri[4]):
                    os.remove(self.veri[4])
                log_ekle(conn, self.veri[0], "SİLME", f"Açıklama: {self.veri[1]}")
                conn.execute("DELETE FROM esyalar WHERE id=?", (self.veri[0],))
                conn.commit()
            self.toast_fonk("Kayıt silindi.", "basari")
        except (sqlite3.Error, OSError) as e:
            self.toast_fonk(f"Silme hatası: {e}", "hata")
        self.yenile_fonk()
        self.destroy()


# ── Giriş noktası ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = ProfoundApp(root)
    root.mainloop()
