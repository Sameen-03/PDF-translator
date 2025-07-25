# 📄 PDF Translator with Local LLM (Ollama + Marker + MarkdownPDF)

This project provides a complete pipeline for translating PDF documents into other languages using a **local Large Language Model (LLM)**. It extracts structured text and images from a PDF, translates the text into the target language using Ollama, and regenerates a new translated PDF — all while preserving layout and formatting.

---

## 🚀 Features

- 🔍 Extracts text and images from PDFs using [`marker`](https://github.com/zero-one-group/marker)
- 🌐 Translates text to **any target language** using a local LLM via [`ollama`](https://ollama.com/)
- 📄 Reconstructs translated content into a well-formatted PDF using `markdown-pdf`
- 💾 Saves extracted and translated text as `.md` files for readability and further use
- ✅ Lightweight, offline-friendly, and privacy-preserving

---

## 🛠️ Tech Stack

- `marker`: PDF layout-aware text & image extraction
- `ollama`: Run LLMs like `gemma`, `mistral`, etc. locally
- `markdown-pdf`: Convert translated Markdown to a clean, printable PDF
- `Python`: File handling, automation, and orchestration

---

## 📂 Project Structure

