import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfReader, PdfWriter
import re
import io
import os
import zipfile
from collections import OrderedDict

st.set_page_config(page_title="Separador de Ordens", page_icon="", layout="wide")

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); min-height: 100vh; }
    .main-title { font-size: 2.5rem; font-weight: 700; background: linear-gradient(90deg, #64b5f6, #42a5f5, #1e88e5); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 8px; }
    .subtitle { color: rgba(255, 255, 255, 0.6); text-align: center; font-size: 1.1rem; margin-bottom: 40px; }
    .order-card { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 24px; margin: 12px 0; }
    .stButton>button { background: linear-gradient(135deg, #1e88e5, #1565c0) !important; color: white !important; border: none !important; border-radius: 12px !important; padding: 12px 24px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📄 Separador de Ordens de Serviço</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Faça upload do PDF escaneado e separe automaticamente cada ordem em arquivos individuais</div>', unsafe_allow_html=True)

def extrair_texto_ocr(imagem):
    return pytesseract.image_to_string(imagem, lang='por')

def eh_nova_ordem(texto):
    match = re.search(r'Ordem\s+(\d{9})\s+Tipo', texto, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'ORDEM\s+(\d{9})\s+TIPO', texto)
    if match:
        return match.group(1)
    return None

def processar_pdf(pdf_bytes):
    images = convert_from_bytes(pdf_bytes, dpi=300)
    total_paginas = len(images)
    ordens = OrderedDict()
    ordem_atual = None
    
    for i, imagem in enumerate(images):
        texto = extrair_texto_ocr(imagem)
        nova_ordem = eh_nova_ordem(texto)
        
        if nova_ordem:
            ordem_atual = nova_ordem
            if ordem_atual not in ordens:
                ordens[ordem_atual] = []
            ordens[ordem_atual].append(i)
        elif ordem_atual:
            ordens[ordem_atual].append(i)
    
    return ordens, total_paginas, images

def criar_pdf_separado(images, indices_paginas):
    writer = PdfWriter()
    for idx in indices_paginas:
        img_byte_arr = io.BytesIO()
        images[idx].save(img_byte_arr, format='PDF')
        img_byte_arr.seek(0)
        reader = PdfReader(img_byte_arr)
        writer.add_page(reader.pages[0])
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output

def criar_zip_com_todos(ordens_dados):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for nome_ordem, pdf_bytes in ordens_dados.items():
            zip_file.writestr(f"{nome_ordem}.pdf", pdf_bytes.getvalue())
    zip_buffer.seek(0)
    return zip_buffer

uploaded_file = st.file_uploader("📎 Arraste o PDF aqui ou clique para selecionar", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.getvalue()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Arquivo", uploaded_file.name[:18])
    with col2:
        st.metric("Tamanho", f"{len(pdf_bytes)/1024:.0f} KB")
    with col3:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        st.metric("Páginas", len(reader.pages))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 Separar Ordens", type="primary", use_container_width=True):
        progress_bar = st.progress(0, text="Processando...")
        status_text = st.empty()
        
        status_text.info("🔄 Convertendo PDF em imagens e analisando com OCR...")
        
        ordens, total_paginas, images = processar_pdf(pdf_bytes)
        
        progress_bar.progress(1.0, text="Concluído!")
        status_text.empty()
        
        if not ordens:
            st.error("❌ Nenhuma ordem foi identificada.")
        else:
            st.success(f"✅ **{len(ordens)} ordens** encontradas em **{total_paginas} páginas**!")
            st.markdown("<br>", unsafe_allow_html=True)
            
            ordens_dados = {}
            for num_ordem, paginas in ordens.items():
                ordens_dados[num_ordem] = criar_pdf_separado(images, paginas)
            
            zip_data = criar_zip_com_todos(ordens_dados)
            
            st.download_button(
                label="📦 Baixar Todas as Ordens (ZIP)",
                data=zip_data,
                file_name="Ordens_Separadas.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📋 Ordens Encontradas")
            
            for num_ordem, paginas in ordens.items():
                pdf_separado = ordens_dados[num_ordem]
                st.markdown(f"""
                <div class="order-card">
                    <h3 style="margin: 0; color: #64b5f6;">📄 Ordem {num_ordem}</h3>
                    <p style="margin: 4px 0 0 0; color: rgba(255,255,255,0.6); font-size: 0.9rem;">
                        Páginas: {', '.join([str(p+1) for p in paginas])} • Total: {len(paginas)} página(s)
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.download_button(
                        label="⬇️ Baixar",
                        data=pdf_separado,
                        file_name=f"{num_ordem}.pdf",
                        mime="application/pdf",
                        key=f"btn_{num_ordem}",
                        use_container_width=True
                    )