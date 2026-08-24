import streamlit as st
import requests
import random
import json
import google.generativeai as genai

st.set_page_config(page_title="Mi Recomendador", page_icon="📚", layout="wide")

# === 🎨 MAGIA ESTÉTICA (Sutil y Limpia) ===
st.markdown("""
<style>
/* 1. Importar tipografías de Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&family=Nunito:wght@400;700&display=swap');

/* 2. Cambiar la letra de la web */
html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Lora', serif !important;
}

/* 3. Efecto sutil de movimiento en los botones */
div.stButton > button {
    transition: transform 0.2s ease-in-out;
}
div.stButton > button:hover {
    transform: scale(1.02);
}
</style>
""", unsafe_allow_html=True)

NOTION_TOKEN = st.secrets["notion_token"]
DATABASE_ID = st.secrets["database_id"]

# --- FUNCIONES DE EXTRACCIÓN DE NOTION ---
def obtener_titulo(prop):
    try:
        titulo_real = prop["title"][0]["plain_text"]
        return titulo_real if titulo_real.strip() else "Sin título"
    except: return "Sin título"

def obtener_estado(prop):
    try:
        if prop["type"] == "status": return prop["status"]["name"].lower()
        if prop["type"] == "select": return prop["select"]["name"].lower()
    except: return ""
    return ""

def obtener_ids(prop):
    if not prop: return []
    try:
        if prop["type"] == "relation": return [r["id"] for r in prop["relation"]]
        if prop["type"] == "multi_select": return [m["id"] for m in prop["multi_select"]]
        if prop["type"] == "select" and prop["select"]: return [prop["select"]["id"]]
    except: pass
    return []

def obtener_texto_formula(prop):
    try:
        if prop["type"] == "formula": return prop["formula"].get("string", "")
    except: return ""
    return ""

def obtener_numero(prop):
    if not prop: return None
    try:
        tipo = prop.get("type")
        if tipo == "number": return prop.get("number")
        if tipo == "formula": return prop.get("formula", {}).get("number") or prop.get("formula", {}).get("string")
        if tipo == "rich_text" and prop.get("rich_text"): return prop["rich_text"][0]["plain_text"]
    except: return None
    return None

def obtener_multiselect(prop):
    try:
        if prop["type"] == "multi_select": return [c["name"] for c in prop["multi_select"]]
    except: return []
    return []

def obtener_checkbox(prop):
    try:
        if prop["type"] == "checkbox": return prop["checkbox"]
    except: return False
    return False

def obtener_descripcion(prop):
    try:
        if prop["type"] == "rich_text" and prop["rich_text"]:
            return "".join([t["plain_text"] for t in prop["rich_text"]])
    except: return ""
    return ""

def obtener_portada(prop):
    try:
        archivos = prop.get("files", [])
        if archivos:
            return archivos[0]["file"]["url"] if "file" in archivos[0] else archivos[0]["external"]["url"]
    except: pass
    return None

def safe_float(val):
    try: return float(val)
    except: return 9999.0

def primeras_de_saga(lista_candidatos):
    sagas = {}
    for libro in lista_candidatos:
        saga = libro.get("saga_texto")
        num = libro.get("numero_saga")
        if saga and num is not None:
            n = safe_float(num)
            if saga not in sagas or n < sagas[saga]["n"]:
                sagas[saga] = {"n": n, "libro": libro}
    return [v["libro"] for v in sagas.values()]

def formato_mensaje(rec):
    if rec.get("es_por_terminar", False):
        mensaje = f"¿Y si retomas este libro?\n\n**{rec['titulo']}**, de {rec['autor_texto']}."
    else:
        mensaje = f"Prueba con **{rec['titulo']}**, de {rec['autor_texto']}."
        
    if rec['saga_texto']:
        num = rec['numero_saga']
        num_texto = f" (Libro {int(float(num))})" if (num and str(num).replace('.','',1).isdigit()) else ""
        mensaje += f" \n*Pertenece a {rec['saga_texto']}{num_texto}*"
    return mensaje

# --- MAGIA VISUAL: EL POP-UP ---
@st.dialog("🎉 ¡Aquí tienes tu próxima lectura!")
def mostrar_popup(libro, titular, mensaje_extra=""):
    st.markdown(f"### {titular}")
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        url_img = libro.get("portada_url")
        if url_img:
            st.markdown(
                f'''
                <style>
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(10px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                .portada-animada {{
                    width: 100%;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                    animation: fadeIn 0.6s ease-out forwards;
                }}
                </style>
                <img src="{url_img}" class="portada-animada">
                ''', unsafe_allow_html=True)
        else:
            st.info("🖼️ Sin portada")
            
    with col2:
        st.markdown(formato_mensaje(libro))
        if mensaje_extra: st.info(f"✨ {mensaje_extra}")
            
        tags = []
        if libro.get("ritmos"): tags.append(f"⏱️ {libro['ritmos'][0]}")
        if libro.get("tonos"): tags.append(f"🎭 {libro['tonos'][0]}")
        if libro.get("narradores"): tags.append(f"🗣️ {libro['narradores'][0]}")
        if tags: st.caption(" | ".join(tags))
            
        if libro.get("descripcion"):
            with st.expander("📖 Leer sinopsis"):
                st.write(libro["descripcion"])
    
    if st.button("Cerrar", use_container_width=True):
        st.rerun()

# --- INICIO DE LA APP Y EL BANNER ---

st.markdown("""
<div style="
    background: linear-gradient(rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.3)), url('https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=1200&q=80') center/cover;
    border-radius: 12px;
    padding: 60px 20px;
    text-align: center;
    margin-bottom: 30px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
">
    <h1 style="color: white !important; margin: 0; font-size: 3em; font-family: 'Lora', serif; text-shadow: 2px 2px 8px rgba(0,0,0,0.9), 0px 0px 20px rgba(0,0,0,0.7);">
        📚 Mi Recomendador de Lectura
    </h1>
    <p style="color: #f8f9fa; font-size: 1.2em; margin-top: 10px; font-family: 'Nunito', sans-serif; text-shadow: 1px 1px 5px rgba(0,0,0,0.9);">
        Encuentra tu próxima gran aventura literaria
    </p>
</div>
""", unsafe_allow_html=True)

try:
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    
    leidos, por_terminar, pendientes = [], [], []
    diccionario_libros = {}
    autores_leidos_ids = set() 
    
    with st.spinner('Cargando estantería completa...'):
        has_more = True
        next_cursor = None
        while has_more:
            payload = {"page_size": 100}
            if next_cursor: payload["start_cursor"] = next_cursor
            
            try: respuesta = requests.post(url, headers=headers, json=payload, timeout=15)
            except requests.exceptions.Timeout:
                st.error("⚠️ Conexión lenta. Recarga la página.")
                st.stop()
                
            if respuesta.status_code == 200:
                datos = respuesta.json()
                for libro in datos.get("results", []):
                    props = libro["properties"]
                    titulo = obtener_titulo(props.get("Título", {}))
                    if titulo == "Sin título": continue
                    
                    estado_lower = obtener_estado(props.get("Estado", {})).strip()
                    
                    info_libro = {
                        "titulo": titulo,
                        "autor_texto": obtener_texto_formula(props.get("Texto Autor", {})),
                        "saga_texto": obtener_texto_formula(props.get("Texto Saga", {})),
                        "numero_saga": obtener_numero(props.get("Nº Saga", {})),
                        "colores": obtener_multiselect(props.get("Color", {})),
                        "ritmos": obtener_multiselect(props.get("Ritmo", {})),
                        "tonos": obtener_multiselect(props.get("Tono", {})),
                        "narradores": obtener_multiselect(props.get("Narrador", {})),
                        "generos": obtener_ids(props.get("Género", {})),
                        "autores_ids": obtener_ids(props.get("Autor", {})),
                        "descripcion": obtener_descripcion(props.get("Descripción", {})),
                        "portada_url": obtener_portada(props.get("Portada", {})),
                        "es_por_terminar": False,
                        "es_ingles": obtener_checkbox(props.get("Inglés", {}))
                    }
                    
                    nombre_visual = f"{titulo}, de {info_libro['autor_texto']}" if info_libro['autor_texto'] else titulo
                    diccionario_libros[nombre_visual] = info_libro
                    
                    if estado_lower == "leído":
                        leidos.append(nombre_visual)
                        for a_id in info_libro["autores_ids"]: autores_leidos_ids.add(a_id)
                    elif estado_lower == "por terminar":
                        info_libro["es_por_terminar"] = True
                        por_terminar.append(info_libro)
                    elif estado_lower == "leyendo":
                        pass 
                    elif estado_lower == "por leer":
                        pendientes.append(info_libro)
                    else:
                        pendientes.append(info_libro) 
                
                has_more = datos.get("has_more", False)
                next_cursor = datos.get("next_cursor", None)
            else: break

    leidos.sort()
    candidatos = pendientes + por_terminar
    
    st.subheader("🎯 Tu punto de partida")
    libro_elegido = st.selectbox("Elige el último libro que te encantó:", leidos)
    ref = diccionario_libros[libro_elegido]
    
    # === EL ESCAPARATE ===
    st.markdown("<br>", unsafe_allow_html=True)
    esc_col1, esc_col2 = st.columns([1.2, 3])
    with esc_col1:
        if ref.get("portada_url"):
            st.markdown(
                f'''
                <div style="display: flex; justify-content: center;">
                    <img src="{ref["portada_url"]}" style="width: 100%; max-width: 220px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">
                </div>
                ''', 
                unsafe_allow_html=True
            )
        else:
            st.info("🖼️ Sin portada")
            
    with esc_col2:
        st.markdown(f"## {ref['titulo']}")
        st.markdown(f"**✍️ {ref['autor_texto']}**")
        
        tags_ref = []
        if ref.get("ritmos"): tags_ref.append(f"⏱️ {ref['ritmos'][0]}")
        if ref.get("tonos"): tags_ref.append(f"🎭 {ref['tonos'][0]}")
        if ref.get("narradores"): tags_ref.append(f"🗣️ {ref['narradores'][0]}")
        if tags_ref: st.caption(" | ".join(tags_ref))
            
        if ref.get("descripcion"):
            with st.expander("📖 Leer sinopsis completa"):
                st.write(ref["descripcion"])
            
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    
    # === LA MAGIA DE LAS PESTAÑAS ===
    tab1, tab2, tab3 = st.tabs(["⚡ Búsqueda Rápida", "🍹 La Coctelera", "🔮 El Oráculo"])
    
    with tab1:
        st.markdown("#### 🎲 Opciones Rápidas")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("🔮 Mismo género", use_container_width=True):
                g_ref, a_ref = set(ref["generos"]), set(ref["autores_ids"])
                if not g_ref: st.warning("Sin géneros asignados.")
                else:
                    cands = [p for p in candidatos if not set(p["autores_ids"]).intersection(a_ref)]
                    exactas = [p for p in cands if set(p["generos"]) == g_ref]
                    expandidas = [p for p in cands if g_ref.issubset(set(p["generos"])) and set(p["generos"]) != g_ref]
                    concentradas = [p for p in cands if set(p["generos"]).issubset(g_ref) and len(set(p["generos"])) > 0 and set(p["generos"]) != g_ref]
                    
                    if exactas: mostrar_popup(random.choice(exactas), "🔥 Match Exacto (100% pureza)")
                    elif expandidas: mostrar_popup(random.choice(expandidas), "✨ Match Expandido")
                    elif concentradas: mostrar_popup(random.choice(concentradas), "🎯 Match Concentrado")
                    else: st.warning("No hay libros pendientes que igualen esta pureza.")

        with col2:
            if st.button("✍️ Mismo autor", use_container_width=True):
                opciones = [p for p in candidatos if set(p["autores_ids"]).intersection(set(ref["autores_ids"]))]
                if opciones: mostrar_popup(random.choice(opciones), "Siguiendo con su pluma:")
                else: st.warning("No te quedan libros pendientes de este autor.")

        with col3:
            if st.button("🔄 Cambio radical", use_container_width=True):
                opciones = [p for p in candidatos if not any(g in p["generos"] for g in ref["generos"])]
                if opciones: mostrar_popup(random.choice(opciones), "Rompe con todo:")
                else: st.warning("¡Añade más variedad a tus pendientes!")
                
        with col4:
            if st.button("🇬🇧 En Inglés", use_container_width=True):
                opciones = [p for p in candidatos if p.get("es_ingles", False)]
                if opciones: mostrar_popup(random.choice(opciones), "Para tu reto de lectura:")
                else: st.warning("No tienes pendientes marcados en inglés.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🔍 Opciones Avanzadas")
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            if st.button("🔗 Continuar Saga", use_container_width=True):
                if not ref.get("saga_texto"): st.warning("No pertenece a ninguna saga.")
                else:
                    opciones = [p for p in candidatos if p.get("saga_texto") == ref.get("saga_texto") and p.get("numero_saga") is not None]
                    if opciones:
                        siguiente = min(opciones, key=lambda x: safe_float(x["numero_saga"]))
                        mostrar_popup(siguiente, "El viaje continúa:")
                    else: st.warning("¡Felicidades! Estás al día.")
                        
        with col6:
            if st.button("📚 Saga Similar", use_container_width=True):
                cands_saga = [p for p in candidatos if p.get("saga_texto") and p.get("saga_texto") != ref.get("saga_texto") and len(set(ref["generos"]).intersection(set(p["generos"]))) >= 1]
                opciones = primeras_de_saga(cands_saga)
                if opciones: mostrar_popup(random.choice(opciones), "Empieza una nueva aventura:")
                else: st.warning("No hay nuevas sagas de este género listas para empezar.")

        with col7:
            if st.button("🎨 Buscar por Color", use_container_width=True):
                opciones = [p for p in candidatos if set(p.get("colores", [])).intersection(set(ref.get("colores", [])))]
                if opciones: mostrar_popup(random.choice(opciones), "Estética compartida:")
                else: st.warning("No hay libros pendientes con esta paleta de colores.")

        with col8:
            if st.button("🌫️ Misma Atmósfera (Gemini)", use_container_width=True):
                if not ref.get("descripcion") or len(ref.get("descripcion")) < 20: st.warning("Sin descripción suficiente.")
                else:
                    cands_validos = [p for p in candidatos if p.get("descripcion") and len(p.get("descripcion")) > 20 and not set(p["autores_ids"]).intersection(set(ref["autores_ids"]))]
                    if not cands_validos: cands_validos = [p for p in candidatos if p.get("descripcion") and len(p.get("descripcion")) > 20]
                    if not cands_validos: st.warning("No tienes pendientes con descripción para analizar.")
                    else:
                        with st.spinner("🧠 Gemini está analizando..."):
                            try:
                                genai.configure(api_key=st.secrets["gemini_api_key"])
                                model = genai.GenerativeModel('gemini-3.5-flash-lite')
                                prompt = f"LIBRO: {ref['titulo']}\nSINOPSIS: {ref['descripcion']}\nCANDIDATOS:\n"
                                for i, c in enumerate(cands_validos): prompt += f"[{i}] {c['titulo']}\nSinopsis: {c['descripcion']}\n"
                                prompt += 'Devuelve JSON: {"indice": int, "explicacion": "texto"}'
                                res = model.generate_content(prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json"))
                                res_json = json.loads(res.text)
                                if 0 <= int(res_json["indice"]) < len(cands_validos):
                                    mostrar_popup(cands_validos[int(res_json["indice"])], "🧠 Recomendación de Gemini", res_json["explicacion"])
                                else: st.error("Índice inválido.")
                            except Exception as e: st.error(f"Error Gemini: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💥 Emociones y Sensaciones")
        col9, col10, col11, col12 = st.columns(4)
        with col9:
            if st.button("🩸 Sangre Nueva", use_container_width=True):
                opciones = [p for p in candidatos if not any(a_id in autores_leidos_ids for a_id in p["autores_ids"])]
                if opciones: mostrar_popup(random.choice(opciones), "Explora nuevos horizontes:")
                else: st.warning("¡Ya has leído a todos tus autores pendientes!")
        with col10:
            if st.button("🎲 Ruleta Rusa", use_container_width=True):
                if candidatos: mostrar_popup(random.choice(candidatos), "La suerte está echada:")
                else: st.warning("No te quedan libros pendientes.")
        with col11:
            if st.button("⏱️ Mismo Ritmo", use_container_width=True):
                r_ref = set(ref.get("ritmos", []))
                if not r_ref: st.warning("Este libro no tiene Ritmo.")
                else:
                    opciones = [p for p in candidatos if set(p.get("ritmos", [])).intersection(r_ref)]
                    if opciones: mostrar_popup(random.choice(opciones), f"Al mismo compás ({', '.join(r_ref)}):")
                    else: st.warning("No hay pendientes con este ritmo.")
        with col12:
            if st.button("🎭 Mismo Tono", use_container_width=True):
                t_ref = set(ref.get("tonos", []))
                if not t_ref: st.warning("Este libro no tiene Tono.")
                else:
                    opciones = [p for p in candidatos if set(p.get("tonos", [])).intersection(t_ref)]
                    if opciones: mostrar_popup(random.choice(opciones), f"Con la misma vibra ({', '.join(t_ref)}):")
                    else: st.warning("No hay pendientes con este tono.")

        col13, col14, col15, col16 = st.columns(4)
        with col13:
            if st.button("🗣️ Mismo Narrador", use_container_width=True):
                n_ref = set(ref.get("narradores", []))
                if not n_ref: st.warning("Este libro no tiene Narrador asignado.")
                else:
                    opciones = [p for p in candidatos if set(p.get("narradores", [])).intersection(n_ref)]
                    if opciones: mostrar_popup(random.choice(opciones), f"A través de sus ojos ({', '.join(n_ref)}):")
                    else: st.warning("No hay pendientes con este narrador.")

    with tab2:
        st.markdown("### 🍹 La Coctelera Literaria")
        st.write("Mezcla todas las condiciones que debe cumplir tu próxima lectura basándose en el libro que tienes seleccionado arriba:")
        
        st.markdown("<br>", unsafe_allow_html=True)
        cx1, cx2, cx3 = st.columns(3)
        with cx1:
            f_genero = st.checkbox("🔮 Mismo género")
            f_autor = st.checkbox("✍️ Mismo autor")
        with cx2:
            f_ritmo = st.checkbox("⏱️ Mismo ritmo")
            f_tono = st.checkbox("🎭 Mismo tono")
            f_narrador = st.checkbox("🗣️ Mismo narrador")
        with cx3:
            f_color = st.checkbox("🎨 Mismo color")
            f_ingles = st.checkbox("🇬🇧 En inglés")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🍸 Agitar Coctelera", type="primary"):
            filtrados = candidatos.copy()
            
            if f_genero:
                g_ref = set(ref["generos"])
                filtrados = [p for p in filtrados if g_ref.intersection(set(p["generos"]))]
            if f_autor:
                a_ref = set(ref["autores_ids"])
                filtrados = [p for p in filtrados if a_ref.intersection(set(p["autores_ids"]))]
            if f_ritmo:
                r_ref = set(ref.get("ritmos", []))
                filtrados = [p for p in filtrados if r_ref.intersection(set(p.get("ritmos", [])))]
            if f_tono:
                t_ref = set(ref.get("tonos", []))
                filtrados = [p for p in filtrados if t_ref.intersection(set(p.get("tonos", [])))]
            if f_narrador:
                n_ref = set(ref.get("narradores", []))
                filtrados = [p for p in filtrados if n_ref.intersection(set(p.get("narradores", [])))]
            if f_color:
                c_ref = set(ref.get("colores", []))
                filtrados = [p for p in filtrados if c_ref.intersection(set(p.get("colores", [])))]
            if f_ingles:
                filtrados = [p for p in filtrados if p.get("es_ingles", False)]
                
            if len(filtrados) > 0:
                ganador = random.choice(filtrados)
                mostrar_popup(ganador, "🍹 ¡Aquí tienes tu cóctel!", "Esta mezcla es exactamente lo que pediste.")
            else:
                st.error("❌ Vaya, ningún libro pendiente cumple TODAS esas condiciones a la vez. ¡Quita algún ingrediente!")

    with tab3:
        st.markdown("### 🔮 El Oráculo de Gemini (Mood Reader)")
        st.write("Olvídate de filtros. Cuéntale a la Inteligencia Artificial cómo te sientes o qué te apetece y ella buscará el libro perfecto.")
        mood_texto = st.text_input("📝 Escribe aquí tu antojo:")
        
        if st.button("✨ Preguntar al Oráculo", type="primary"):
            if not mood_texto: st.warning("¡Escribe algo en la caja!")
            else:
                cands_validos = [p for p in candidatos if p.get("descripcion") and len(p.get("descripcion")) > 20]
                if not cands_validos: st.warning("No hay pendientes con descripción.")
                else:
                    with st.spinner("🔮 El Oráculo está consultando los astros..."):
                        try:
                            genai.configure(api_key=st.secrets["gemini_api_key"])
                            model = genai.GenerativeModel('gemini-3.5-flash-lite')
                            prompt = f'Deseo: "{mood_texto}"\nCANDIDATOS:\n'
                            for i, c in enumerate(cands_validos): prompt += f"[{i}] {c['titulo']}\nSinopsis: {c['descripcion']}\n"
                            prompt += 'JSON: {"indice": int, "explicacion": "texto"}'
                            
                            res = model.generate_content(prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json"))
                            res_json = json.loads(res.text)
                            
                            if 0 <= int(res_json["indice"]) < len(cands_validos):
                                ganador = cands_validos[int(res_json["indice"])]
                                mostrar_popup(ganador, "🔮 El Oráculo ha hablado", res_json["explicacion"])
                            else: st.error("Índice inválido.")
                        except Exception as e: st.error(f"Error Gemini: {e}")

except Exception as e:
    st.error(f"❌ Ups, error al cargar: {e}")