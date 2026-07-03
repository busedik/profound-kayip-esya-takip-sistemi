import os

# ── Dosya / Veritabanı yolları ─────────────────────────────────────────────
DB_YOLU        = "envanter.db"
RESIM_DIZINI   = "esyalar_resimler"

# ── Durum tanımları ────────────────────────────────────────────────────────
DURUMLAR = ["Bulundu", "Teslim Bekliyor", "Teslim Edildi", "Kayıp"]

DURUM_RENKLERI = {
    "Bulundu":         "#2DC653",
    "Teslim Bekliyor": "#F4A261",
    "Teslim Edildi":   "#4361EE",
    "Kayıp":           "#EF233C",
}

# ── Tema renkleri ──────────────────────────────────────────────────────────
RENKLER = {
    "light": {
        "bg":             "#F7F8FC",
        "panel":          "#FFFFFF",
        "sidebar":        "#1E2A4A",
        "sidebar_text":   "#FFFFFF",
        "sidebar_hover":  "#2E3F6A",
        "accent":         "#4361EE",
        "accent2":        "#7209B7",
        "success":        "#2DC653",
        "danger":         "#EF233C",
        "warning":        "#F4A261",
        "text":           "#1B1B2F",
        "subtext":        "#6B7280",
        "border":         "#E5E7EB",
        "input_bg":       "#F9FAFB",
        "row_odd":        "#FFFFFF",
        "row_even":       "#F3F4F6",
        "header_bg":      "#1E2A4A",
        "header_fg":      "#FFFFFF",
        "toast_bg":       "#1B1B2F",
        "toast_fg":       "#FFFFFF",
    },
    "dark": {
        "bg":             "#0F1117",
        "panel":          "#1A1D2E",
        "sidebar":        "#0D0F1A",
        "sidebar_text":   "#E0E0FF",
        "sidebar_hover":  "#1E2340",
        "accent":         "#4CC9F0",
        "accent2":        "#F72585",
        "success":        "#2DC653",
        "danger":         "#FF4560",
        "warning":        "#F4A261",
        "text":           "#E8E8F0",
        "subtext":        "#9CA3AF",
        "border":         "#2D3044",
        "input_bg":       "#1E2140",
        "row_odd":        "#1A1D2E",
        "row_even":       "#141726",
        "header_bg":      "#0D0F1A",
        "header_fg":      "#4CC9F0",
        "toast_bg":       "#E8E8F0",
        "toast_fg":       "#0F1117",
    },
}

# ── Tablo satır tag renkleri ───────────────────────────────────────────────
SATIR_RENKLERI = {
    "Bulundu":         "#E8FAF0",
    "Teslim Bekliyor": "#FFF8ED",
    "Teslim Edildi":   "#EEF2FF",
    "Kayıp":           "#FEE8EA",
}

# ── Klavye kısayolları ─────────────────────────────────────────────────────
KISAYOLLAR = {
    "<Control-n>": "yeni_kayit",
    "<Control-N>": "yeni_kayit",
    "<Delete>":    "secili_sil",
    "<F5>":        "yenile",
    "<Control-f>": "aramaya_odaklan",
    "<Control-F>": "aramaya_odaklan",
    "<Escape>":    "formu_kapat",
}
