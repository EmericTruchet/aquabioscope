"""Thème visuel partagé de l'application (palette "plongée")."""
from __future__ import annotations

ACCENT = "#1298A5"
ACCENT_DARK = "#0E7C86"
ACCENT_DARKER = "#0B6169"
ACCENT_SOFT = "#EAF6F7"
DANGER = "#D64545"
DANGER_DARK = "#B93A3A"
BG = "#F4F7F9"
CARD = "#FFFFFF"
BORDER = "#DCE4E8"
TEXT = "#1F2A33"
TEXT_SECONDARY = "#5B6B73"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}}

QLabel#Title {{
    font-size: 24px;
    font-weight: 600;
    color: {ACCENT_DARK};
}}

QLabel#Subtitle {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}

QLabel#FieldLabel {{
    color: {TEXT_SECONDARY};
    font-weight: 600;
}}

QLineEdit, QDateEdit, QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QPushButton {{
    background: {ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 22px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {ACCENT_DARK}; }}
QPushButton:pressed {{ background: {ACCENT_DARKER}; }}
QPushButton:disabled {{ background: #B7C3C8; }}

QPushButton#SecondaryButton {{
    background: {CARD};
    color: {ACCENT_DARK};
    border: 1px solid {ACCENT};
}}
QPushButton#SecondaryButton:hover {{ background: {ACCENT_SOFT}; }}

QPushButton#DeleteButton {{
    background: {CARD};
    color: {DANGER};
    border: 1px solid {DANGER};
}}
QPushButton#DeleteButton:hover {{ background: #FBEAEA; color: white; background: {DANGER}; }}

QLabel#MainPreview {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QWidget#GalleryThumb {{
    border: 3px solid transparent;
    border-radius: 8px;
}}
QWidget#GalleryThumb[selected="true"] {{
    border: 3px solid {ACCENT};
    background: {ACCENT_SOFT};
}}
QWidget#GalleryThumb QLabel {{
    background: transparent;
}}
QWidget#GalleryThumb QLabel#ThumbCaption {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QWidget#GalleryThumb[selected="true"] QLabel#ThumbCaption {{
    color: {ACCENT_DARK};
    font-weight: 600;
}}

QLabel#HintBar {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

QLabel#FileName {{
    font-weight: 600;
    font-size: 15px;
}}

QLabel#ProgressBadge {{
    background: {ACCENT_SOFT};
    color: {ACCENT_DARK};
    border-radius: 10px;
    padding: 3px 12px;
    font-weight: 600;
}}

QWidget#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
"""
