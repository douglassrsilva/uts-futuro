# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generación de datos sintéticos (Moodle + PeopleSoft)
# MAGIC
# MAGIC Simulamos las **dos fuentes reales** de una universidad y **aterrizamos archivos** (CSV) en
# MAGIC el Volumen `landing`, imitando la llegada de datos de sistemas externos:
# MAGIC
# MAGIC | Sistema | Rol | Tablas (prefijo) |
# MAGIC |---|---|---|
# MAGIC | **Moodle** | LMS (aula virtual) | `mdl_*` — usuarios, cursos, matrículas, entregas, notas, logs |
# MAGIC | **PeopleSoft Campus Solutions** | SIS (sistema académico) | `ps_*` — persona, programa, término, finanzas, admisiones |
# MAGIC
# MAGIC **Idea clave:** este notebook **no crea tablas**, sólo escribe **archivos** en un Volumen.
# MAGIC En el notebook 02, un pipeline con **Auto Loader** los ingiere como Streaming Tables. Es el
# MAGIC patrón de ingestión moderno (desacopla la llegada del dato de su modelado).
# MAGIC
# MAGIC > El mismo alumno existe en **ambos** sistemas con identificadores distintos; el **email**
# MAGIC > es el puente para el MDM (notebook 04).

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Catálogos de referencia (LATAM)
# MAGIC
# MAGIC 8 campus en 8 países, 10 programas (con área **ISCED-F**) y 15 cursos (con prerrequisitos).

# COMMAND ----------

import random
from datetime import datetime, timedelta, timezone
random.seed(42)  # reproducibilidad: mismos datos en cada corrida

# (campus_id, ciudad, país_iso, país_nombre, moneda, lat, lon, vertical, mensualidad_usd, es_sede)
CAMPUS_LATAM = [
    ("LIM", "Lima", "PE", "Perú", "PEN", -12.046, -77.043, "Minería y TIC", 950, True),
    ("BOG", "Bogotá", "CO", "Colombia", "COP", 4.711, -74.072, "Servicios y Fintech", 780, False),
    ("SCL", "Santiago", "CL", "Chile", "CLP", -33.449, -70.669, "Minería y Energía", 1250, False),
    ("MEX", "Ciudad de México", "MX", "México", "MXN", 19.433, -99.133, "Manufactura y Automotriz", 1100, False),
    ("SAO", "São Paulo", "BR", "Brasil", "BRL", -23.551, -46.633, "Agro e Fintech", 1050, False),
    ("BUE", "Buenos Aires", "AR", "Argentina", "ARS", -34.604, -58.382, "Software y Diseño", 720, False),
    ("UIO", "Quito", "EC", "Ecuador", "USD", -0.181, -78.467, "Petróleo y Turismo", 640, False),
    ("MVD", "Montevideo", "UY", "Uruguay", "UYU", -34.901, -56.164, "Agrotech y Servicios", 900, False),
]
PROGRAMAS = [
    ("ING-SIS", "Ingeniería de Sistemas", "06 TIC"), ("ING-IND", "Ingeniería Industrial", "07 Ingeniería"),
    ("ING-CIV", "Ingeniería Civil", "07 Ingeniería"), ("ADM-EMP", "Administración de Empresas", "04 Negocios"),
    ("CONT", "Contabilidad", "04 Negocios"), ("DER", "Derecho", "04 Negocios y Derecho"),
    ("PSIC", "Psicología", "09 Salud y Bienestar"), ("ENF", "Enfermería", "09 Salud y Bienestar"),
    ("ARQ", "Arquitectura", "07 Ingeniería"), ("COM", "Ciencias de la Comunicación", "03 Ciencias Sociales"),
]
CURSOS = [
    ("CALC-I", "Cálculo I", None), ("CALC-II", "Cálculo II", "CALC-I"), ("FIS-I", "Física I", "CALC-I"),
    ("PROG-I", "Programación I", None), ("PROG-II", "Programación II", "PROG-I"), ("EDA", "Estructuras de Datos", "PROG-II"),
    ("BD", "Bases de Datos", "PROG-II"), ("IA", "Inteligencia Artificial", "EDA"), ("EST", "Estadística", "CALC-I"),
    ("ECO", "Economía", None), ("CONTA-I", "Contabilidad I", None), ("MKT", "Marketing", "ECO"),
    ("DER-CIV", "Derecho Civil", None), ("ANAT", "Anatomía", None), ("REDAC", "Redacción Académica", None),
]
NOMBRES = ["Ana","Luis","María","Carlos","Sofía","José","Camila","Diego","Valentina","Mateo",
           "Lucía","Andrés","Daniela","Jorge","Fernanda","Pedro","Gabriela","Ricardo","Paula","Miguel"]
APELLIDOS = ["García","Rodríguez","Martínez","López","Gómez","Pérez","Sánchez","Ramírez","Torres","Flores",
             "Vargas","Castro","Rojas","Díaz","Morales","Ortiz","Silva","Núñez","Mendoza","Herrera"]

# ¿Cuántos estudiantes generar? (el proyecto original usa 6000; puedes bajarlo para ir más rápido)
N_ESTUDIANTES = 6000
print(f"Universo: {N_ESTUDIANTES} estudiantes · {len(CAMPUS_LATAM)} campus · {len(PROGRAMAS)} programas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Helper de escritura al Volumen `landing`
# MAGIC
# MAGIC Cada dataset se escribe como CSV bajo `landing/<tabla>/`. **Limpiamos la carpeta antes** de
# MAGIC escribir: Auto Loader es incremental (append), así que dejar CSVs viejos duplicaría filas al
# MAGIC re-ejecutar. Esto hace el notebook **idempotente**.

# COMMAND ----------

import shutil, os

def escribir_landing(tabla, filas, schema):
    if not filas:
        return
    ruta = f"{LANDING}/{tabla}"
    try:
        if os.path.isdir(ruta):
            shutil.rmtree(ruta)
    except Exception:
        pass
    df = spark.createDataFrame(filas, schema)
    df.coalesce(1).write.mode("overwrite").option("header", "true").csv(ruta)
    print(f"  landing/{tabla}: {len(filas)} filas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. PeopleSoft (SIS) — persona, programa, término, finanzas
# MAGIC
# MAGIC Generamos el núcleo académico-administrativo. Notas en **escala 0-20** (convención LATAM).
# MAGIC ~42 % de estudiantes trabaja (perfil típico de universidades como UTP en Perú).

# COMMAND ----------

base = datetime(2026, 7, 22, tzinfo=timezone.utc)
term = "2026-1"
ps_personal, ps_prog, ps_carterm, ps_fin = [], [], [], []
mdl_users, mdl_enrol = [], []
students = []

for i in range(1, N_ESTUDIANTES + 1):
    emplid = f"S{i:06d}"
    nom, ape = random.choice(NOMBRES), random.choice(APELLIDOS)
    nombre = f"{nom} {ape} {random.choice(APELLIDOS)}"
    camp = random.choices(CAMPUS_LATAM, weights=[26, 14, 12, 14, 14, 8, 6, 6])[0]  # Lima concentra más
    pais = camp[2]
    doc = f"{pais}{random.randint(10**7, 10**8 - 1)}"
    email = f"{nom.lower()}.{ape.lower()}{i}@utsur.edu"          # ← puente para el MDM
    anio_nac = random.randint(1998, 2008)
    genero = random.choice(["F", "M", "X"])
    prog = random.choice(PROGRAMAS)
    gente_trabaja = random.random() < 0.42
    ingreso_anio = random.randint(2019, 2026)
    gpa = round(min(20, max(6, random.gauss(13.8, 2.6))), 2)
    semestre = random.randint(1, 10)
    creditos = semestre * random.randint(18, 24)
    mensualidad = round(camp[8] * random.uniform(0.85, 1.15))
    dias_mora = random.choices([0, 0, 0, 15, 30, 60, 90], weights=[50, 15, 10, 8, 7, 6, 4])[0]

    ps_personal.append((emplid, nombre, doc, email, anio_nac, genero, pais, base))
    ps_prog.append((emplid, prog[0], prog[1], prog[2], camp[0], ingreso_anio,
                    "ACTIVO" if random.random() > 0.06 else "RETIRADO"))
    ps_carterm.append((emplid, term, gpa, creditos, 1 if gente_trabaja else 0, random.randint(3, 6), semestre))
    ps_fin.append((emplid, term, float(mensualidad), int(dias_mora), float(mensualidad * (dias_mora // 30))))
    mdl_uid = 10000 + i
    mdl_users.append((mdl_uid, nom, f"{ape} {random.choice(APELLIDOS)}", email, base))
    students.append(dict(emplid=emplid, mdl_uid=mdl_uid, prog=prog[0], campus=camp[0],
                         gpa=gpa, trabaja=gente_trabaja, riesgo_seed=random.random(), semestre=semestre))

escribir_landing("ps_personal_data", ps_personal,
    "emplid string, nombre string, documento string, email string, anio_nac int, genero string, pais string, load_ts timestamp")
escribir_landing("ps_acad_prog", ps_prog,
    "emplid string, acad_prog string, prog_nombre string, isced_f string, campus string, ingreso_anio int, prog_status string")
escribir_landing("ps_stdnt_car_term", ps_carterm,
    "emplid string, strm string, gpa double, creditos_acum int, gente_trabaja int, cursos_inscritos int, semestre int")
escribir_landing("ps_student_fin", ps_fin,
    "emplid string, strm string, mensualidad double, dias_mora int, saldo_vencido double")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Admisiones — funil de captación (anti-leakage)
# MAGIC
# MAGIC **Importante:** NO generamos "propensión" como dato. La propensión es la **salida de un
# MAGIC modelo** (notebook 06), no una columna de entrada. Aquí sólo generamos **atributos
# MAGIC pre-decisión** (canal, puntaje, programa, campus, ciclo) y un **desenlace** (etapa del funil)
# MAGIC *causado* por esos atributos + ruido, para que el modelo pueda aprender la relación real.
# MAGIC El `ciclo` distingue histórico (2024/2025 = entrenar) de actual (2026 = scorear).

# COMMAND ----------

CANALES = ["Orgánico", "Google Ads", "Meta Ads", "Feria educativa", "Referido", "Convenio colegio"]
CANAL_INTENCION = {"Referido": 1.25, "Convenio colegio": 1.25, "Feria educativa": 1.15,
                   "Orgánico": 1.0, "Google Ads": 0.9, "Meta Ads": 0.85}
adm_rows, aid_seq = [], 0
for camp in CAMPUS_LATAM:
    n_mat = sum(1 for s in students if s["campus"] == camp[0])
    n_post = int(max(50, n_mat * 2.6))
    camp_boost = 1.08 if camp[9] else 1.0
    for _ in range(n_post):
        aid_seq += 1
        prog = random.choice(PROGRAMAS)
        canal = random.choices(CANALES, weights=[25, 22, 18, 12, 14, 9])[0]
        puntaje = round(random.uniform(8, 20), 1)
        ciclo = random.choices([2024, 2025, 2026], weights=[40, 40, 20])[0]
        p = (puntaje / 20) * CANAL_INTENCION[canal] * camp_boost + random.gauss(0, 0.12)  # prob. LATENTE (no se guarda)
        r = random.random() * 1.05
        etapa = ("MATRICULÓ" if r < p * 0.5 else "ADMITIDO" if r < p * 0.72
                 else "POSTULÓ" if r < p * 0.9 + 0.3 else "PROSPECTO")
        adm_rows.append((f"A{aid_seq:07d}", camp[0], camp[2], prog[0], prog[1], canal, puntaje, etapa, ciclo))

escribir_landing("ps_adm_appl_data", adm_rows,
    "appl_id string, campus string, pais string, acad_prog string, prog_nombre string, canal string, puntaje_admision double, etapa_funil string, ciclo_admision int")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Moodle (LMS) — cursos, matrículas, entregas, notas y eventos Caliper
# MAGIC
# MAGIC Los **logs** simulan eventos **Caliper** (estándar 1EdTech de analítica de aprendizaje): son
# MAGIC la señal de *compromiso* del alumno. Generamos **menos** eventos para quienes están en riesgo
# MAGIC (`riesgo_seed` alto) — así el modelo de deserción (notebook 05) tendrá señal real que aprender.

# COMMAND ----------

mdl_courses = [(CURSOS.index(c) + 100, c[0], c[1], c[2] or "", "2026-1") for c in CURSOS]
escribir_landing("mdl_course", mdl_courses,
    "courseid int, shortname string, fullname string, prereq string, term string")

assigns, submissions, grades, logs = [], [], [], []
aid = 1
course_assigns = {}
for c in mdl_courses:
    for k in range(2):  # 2 tareas por curso (la 1ª tipo 'essay' → base del AES)
        course_assigns.setdefault(c[0], []).append(aid)
        assigns.append((aid, c[0], f"Tarea {k+1} · {c[2]}", "essay" if k == 0 else "quiz",
                        base - timedelta(days=random.randint(10, 60))))
        aid += 1
escribir_landing("mdl_assign", assigns, "assignid int, courseid int, name string, tipo string, duedate timestamp")

for s in students:
    for c in random.sample(mdl_courses, random.randint(4, 6)):  # cada alumno cursa 4-6 cursos
        mdl_enrol.append((s["mdl_uid"], c[0], base - timedelta(days=random.randint(30, 120)), "student"))
        n_events = max(1, int(random.gauss(40 if s["riesgo_seed"] > 0.3 else 12, 10)))
        for _ in range(n_events):
            ts = base - timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))
            logs.append((s["mdl_uid"], c[0], random.choice(["viewed", "submitted", "navigated", "loggedin"]),
                         "AssignableDigitalResource" if random.random() > .5 else "Page", ts))
        for a in course_assigns.get(c[0], []):
            if random.random() > (0.35 if s["riesgo_seed"] > 0.4 else 0.05):  # entregó
                submissions.append((a, s["mdl_uid"], base - timedelta(days=random.randint(0, 30)),
                                    "submitted", random.randint(200, 1500)))
                nota = round(min(20, max(0, random.gauss(s["gpa"], 2.5))), 1)
                grades.append((a, s["mdl_uid"], c[0], nota, base))

escribir_landing("mdl_user", mdl_users, "userid int, firstname string, lastname string, email string, load_ts timestamp")
escribir_landing("mdl_user_enrolments", mdl_enrol, "userid int, courseid int, timeenrolled timestamp, role string")
escribir_landing("mdl_assign_submission", submissions, "assignid int, userid int, timemodified timestamp, status string, longitud int")
escribir_landing("mdl_grades", grades, "assignid int, userid int, courseid int, nota double, timemodified timestamp")
escribir_landing("mdl_logstore_standard_log", logs, "userid int, courseid int, action string, target string, timecreated timestamp")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Referencia — geografía y capacidad por campus, e histórico de matrícula
# MAGIC
# MAGIC La **capacidad** de recursos (aulas, energía, laboratorios, comedor, dormitorios) no es
# MAGIC uniforme: depende de la **fase de la carrera** del alumno. Un alumno inicial (sem 1-2) llena
# MAGIC aulas y comedor; uno final (sem 7-10) usa laboratorios especializados. Estos coeficientes
# MAGIC (`PHASE_COEF`) alimentan el **Digital Twin** del campus (notebook 07 / app).

# COMMAND ----------

geo = [(c[0], c[1], c[2], c[3], c[4], float(c[5]), float(c[6]), c[7], int(c[8]), 1 if c[9] else 0)
       for c in CAMPUS_LATAM]
escribir_landing("campus_geo", geo,
    "campus_id string, ciudad string, pais string, pais_nombre string, moneda string, lat double, lon double, vertical string, mensualidad_usd int, es_sede int")

BASE_DEM = {"salas": 1/35, "energia": 4.2, "restaurante": 0.62, "labs": 1/90, "dorms": 0.18}
PHASE_COEF = {
    "salas":       {"inicial": 1.30, "media": 1.00, "final": 0.55},
    "energia":     {"inicial": 0.90, "media": 1.00, "final": 1.20},
    "restaurante": {"inicial": 1.25, "media": 1.00, "final": 0.70},
    "labs":        {"inicial": 0.35, "media": 1.00, "final": 2.10},
    "dorms":       {"inicial": 1.40, "media": 1.00, "final": 0.65},
}
_fase = lambda sem: "inicial" if sem <= 2 else "media" if sem <= 6 else "final"
HOLGURA = 0.70  # ocupación objetivo en la base → holgura para crecer sin déficit fantasma
cap = []
for c in CAMPUS_LATAM:
    comp = {"inicial": 0, "media": 0, "final": 0}
    for s in [s for s in students if s["campus"] == c[0]]:
        comp[_fase(s["semestre"])] += 1
    if sum(comp.values()) == 0:
        comp = {"inicial": 33, "media": 34, "final": 33}
    dem = lambda res: BASE_DEM[res] * sum(comp[f] * PHASE_COEF[res][f] for f in comp)
    cap.append((c[0], int(dem("salas")/HOLGURA), 35, int(dem("energia")/HOLGURA), 4.2,
                int(dem("restaurante")/HOLGURA), 0.62, int(dem("labs")/HOLGURA), 90,
                int(dem("dorms")/HOLGURA), 0.18, comp["inicial"], comp["media"], comp["final"]))
escribir_landing("campus_capacity", cap,
    "campus_id string, salas_capacidad int, alumnos_por_sala int, energia_kwh_capacidad int, "
    "kwh_por_alumno double, comedor_capacidad int, comidas_por_alumno double, labs_capacidad int, "
    "alumnos_por_lab int, camas_capacidad int, ratio_dormitorio double, n_inicial int, n_media int, n_final int")

hist = []
SEMS = ["2022-1","2022-2","2023-1","2023-2","2024-1","2024-2","2025-1","2025-2","2026-1"]
for c in CAMPUS_LATAM:
    base_n = sum(1 for s in students if s["campus"] == c[0]) or 100
    for k, sem in enumerate(SEMS):
        val = int(base_n * (0.72 + 0.04*k) * (1.06 if sem.endswith("-1") else 0.97) * random.uniform(0.96, 1.04))
        hist.append((c[0], c[2], sem, k, val))
escribir_landing("matricula_historica", hist,
    "campus_id string, pais string, strm string, periodo_idx int, matricula int")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Redacciones (AES) y papers académicos
# MAGIC
# MAGIC Para el **Automated Essay Scoring** (notebook 09) y el **GraphRAG de investigación**
# MAGIC (notebook 10) generamos redacciones de estudiantes y papers como **PDFs reales** (sin
# MAGIC dependencias externas). La `nota_humana` refleja la **calidad del texto** (no el GPA), para
# MAGIC que la calibración QWK del AES sea significativa.
# MAGIC
# MAGIC `_mini_pdf` construye un PDF válido byte a byte con `WinAnsiEncoding` (para que los acentos
# MAGIC á/é/í/ó/ú/ñ se rendericen bien y el OCR los lea correctamente).

# COMMAND ----------

def _mini_pdf(titulo, autores, anio, abstract, secciones):
    """PDF válido multi-página sin librerías externas. Devuelve bytes."""
    esc = lambda s: s.replace("\\", "").replace("(", "").replace(")", "")
    def wrap(txt, n=92):
        out = []
        for para in txt.split("\n"):
            line = ""
            for w in para.split(" "):
                if len(line) + len(w) + 1 > n:
                    out.append(line); line = w
                else:
                    line = (line + " " + w).strip()
            out.append(line)
        return out
    lines = [("H", titulo), ("S", f"{autores}  ·  {anio}  ·  Universidad Tecnológica de Sudamérica"), ("B", "Abstract")]
    lines += [("T", l) for l in wrap(abstract)]
    for sec, cuerpo in secciones:
        lines += [("B", sec)] + [("T", l) for l in wrap(cuerpo)]
    pages, cur = [], []
    for ln in lines:
        cur.append(ln)
        if len(cur) >= 46:
            pages.append(cur); cur = []
    if cur: pages.append(cur)
    def content_stream(pl):
        parts = ["BT", "/F1 11 Tf", "1 0 0 1 56 748 Tm", "14 TL"]
        for kind, txt in pl:
            if kind == "H": parts += ["/F2 17 Tf", "20 TL", f"({esc(txt)[:80]}) Tj", "T*", "/F1 11 Tf", "14 TL"]
            elif kind == "S": parts += ["/F1 9 Tf", f"({esc(txt)[:110]}) Tj", "T*", "T*", "/F1 11 Tf"]
            elif kind == "B": parts += ["/F2 13 Tf", "16 TL", "T*", f"({esc(txt)[:80]}) Tj", "T*", "/F1 11 Tf", "14 TL"]
            else: parts += [f"({esc(txt)[:110]}) Tj", "T*"]
        parts.append("ET")
        return "\n".join(parts).encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i*2} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    for i, pl in enumerate(pages):
        cs = content_stream(pl)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {3+len(pages)*2} 0 R /F2 {4+len(pages)*2} 0 R >> >> /Contents {4 + i*2} 0 R >>".encode())
        objs.append(b"<< /Length " + str(len(cs)).encode() + b" >>\nstream\n" + cs + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    pdf, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(pdf)); pdf += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref_at = len(pdf)
    pdf += f"xref\n0 {len(objs)+1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF".encode()
    return pdf

def escribir_archivo_volumen(vol_path, data):
    """Escribe bytes de forma fiable en un Volumen (Files API; POSIX de respaldo)."""
    try:
        import io
        from databricks.sdk import WorkspaceClient
        WorkspaceClient().files.upload(vol_path, io.BytesIO(data), overwrite=True)
        return
    except Exception:
        pass
    with open(vol_path, "wb") as fh:
        fh.write(data)

# COMMAND ----------

# --- Papers académicos (PDFs → Volumen documentos) ---
try:
    os.makedirs(DOCS, exist_ok=True)
except Exception:
    pass
TEMAS_PAPER = [
    ("Deserción estudiantil en universidades latinoamericanas", "06 TIC",
     "Este estudio analiza los factores predictivos de la deserción universitaria en 8 países de América Latina, combinando señales de compromiso del LMS, rendimiento académico y variables socioeconómicas. Se aplica gradient boosting con explicabilidad SHAP.",
     [("Metodología", "Se recolectaron datos de matrícula, notas y eventos Caliper de 6000 estudiantes: GPA, morosidad, engagement en el LMS y condición de estudiante-trabajador."),
      ("Resultados", "El compromiso en el LMS y la morosidad son los predictores más fuertes. El semestre 5 concentra el mayor riesgo, coincidiendo con la transición al ciclo especializado.")]),
    ("GraphRAG para asistentes académicos: recuperación híbrida", "06 TIC",
     "Presentamos una arquitectura de recuperación aumentada por grafos (GraphRAG) que combina búsqueda semántica vectorial con recorrido de un grafo de conocimiento curricular para responder consultas académicas con citas.",
     [("Arquitectura", "El sistema combina Vector Search sobre chunks de reglamento y cursos con traversal de aristas PREREQUISITE_OF, TAUGHT_IN e IN_AREA."),
      ("Evaluación", "La recuperación híbrida supera a la puramente semántica en preguntas sobre prerrequisitos y rutas de aprendizaje.")]),
    ("Dimensionamiento predictivo de infraestructura universitaria", "07 Ingeniería",
     "Modelamos la demanda de aulas, energía, laboratorios y alojamiento en función del crecimiento de matrícula, habilitando un gemelo digital para la planificación de capacidad multi-campus.",
     [("Modelo", "Regresión sobre series históricas de matrícula por campus, con coeficientes de demanda por recurso y fase de carrera."),
      ("Caso de estudio", "Un crecimiento del 20% satura la capacidad de aulas en los campus de Lima y Ciudad de México.")]),
    ("Optimización del funil de admisiones con propensión de matrícula", "04 Negocios",
     "Desarrollamos un score de propensión de matrícula y un modelo de yield por canal de captación para optimizar la inversión de marketing en admisiones universitarias.",
     [("Método", "Modelo de clasificación sobre postulantes con features de canal, puntaje y comportamiento, entrenado sobre ciclos pasados."),
      ("Impacto", "El canal 'Convenio colegio' presenta el mayor yield; se recomienda reasignar presupuesto.")]),
]
paper_rows = []
for pi, (tit, area, abstract, secs) in enumerate(TEMAS_PAPER, 1):
    autores = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}, {random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
    anio = random.randint(2022, 2026)
    fname = f"paper_{pi:03d}.pdf"
    escribir_archivo_volumen(f"{DOCS}/{fname}", _mini_pdf(tit, autores, anio, abstract, secs))
    paper_rows.append((f"P{pi:03d}", tit, autores, anio, area, abstract, f"documentos/{fname}", random.randint(0, 180)))
escribir_landing("paper_catalog", paper_rows,
    "paper_id string, titulo string, autores string, anio int, isced_f string, abstract string, pdf_path string, citas int")
print(f"  papers: {len(paper_rows)} PDFs en {DOCS}")

# COMMAND ----------

# --- Redacciones AES (digital PDF → Volumen essays) + rúbrica ---
# nota_humana = CALIDAD DEL TEXTO (no GPA) → QWK real en la calibración del notebook 09.
TEMAS_ESSAY = [
    ("El impacto de la inteligencia artificial en la educación superior",
     "La inteligencia artificial está redefiniendo la educación superior. Los sistemas de tutoría inteligente permiten personalizar el aprendizaje según el ritmo de cada estudiante. Sin embargo, la dependencia excesiva puede erosionar el pensamiento crítico y la brecha digital amenaza con profundizar desigualdades. En conclusión, su valor depende de la responsabilidad ética con que se implemente.", 16),
    ("Los desafíos de la deserción estudiantil",
     "la desercion es un problema grande. muchos alumnos se van porque no tienen dinero o no entienden las clases. hay que ayudarlos mas, dar mas becas y apoyo psicologico. si no se hace nada el problema sigue igual.", 8),
    ("El valor del aprendizaje basado en datos",
     "El análisis sistemático de datos académicos permite identificar patrones antes invisibles: trayectorias de riesgo y factores de abandono. Es posible anticipar la deserción y activar intervenciones. Pero exige gobernanza sólida: privacidad, seguridad y transparencia algorítmica, para no reproducir sesgos ni penalizar a poblaciones vulnerables.", 18),
    ("Reflexión sobre el trabajo y el estudio simultáneos",
     "trabajar y estudiar al mismo tiempo es muy dificil. no hay tiempo para todo. trabajo de dia y estudio de noche y a veces estoy muy cansado. pero quiero un futuro mejor por eso sigo. la universidad deberia tener horarios flexibles y clases grabadas.", 9),
]
try:
    os.makedirs(ESSAYS, exist_ok=True)
except Exception:
    pass
rubric = [("R1","Tesis y argumentación","Claridad de la tesis y solidez de los argumentos",5),
          ("R2","Organización y coherencia","Estructura lógica, cohesión entre párrafos",5),
          ("R3","Uso del lenguaje","Ortografía, gramática y registro académico",5),
          ("R4","Profundidad y evidencia","Uso de ejemplos, datos y pensamiento crítico",5)]
escribir_landing("essay_rubric", rubric, "criterio_id string, criterio string, descriptor string, peso int")

essay_rows = []
for i, s in enumerate(random.sample(students, 48), 1):
    tema, cuerpo, calidad = random.choice(TEMAS_ESSAY)
    nota_humana = round(min(20, max(2, random.gauss(calidad, 1.3))), 1)
    eid = f"E{i:04d}"; fn = f"essay_{eid}.pdf"
    try:
        escribir_archivo_volumen(f"{ESSAYS}/{fn}", _mini_pdf(tema, s["emplid"], 2026, cuerpo, [("Desarrollo", cuerpo)]))
        archivo = f"essays/{fn}"
    except Exception:
        archivo = ""
    texto_flat = " ".join(cuerpo.split())
    essay_rows.append((eid, s["emplid"], tema, "digital", archivo, texto_flat[:2000], float(nota_humana), "pendiente"))
escribir_landing("essay_submissions", essay_rows,
    "essay_id string, student_id string, tema string, tipo string, archivo string, texto_ocr string, nota_humana double, estado string")
print(f"  essays: {len(essay_rows)} redacciones en {ESSAYS}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Verificación
# MAGIC
# MAGIC Listamos las carpetas aterrizadas en `landing`. En el notebook 02 las ingerimos.

# COMMAND ----------

carpetas = [f.name.rstrip("/") for f in dbutils.fs.ls(LANDING) if not f.name.startswith("_")]
esperadas = {"ps_personal_data", "ps_acad_prog", "ps_stdnt_car_term", "ps_student_fin",
             "ps_adm_appl_data", "mdl_course", "mdl_user", "mdl_user_enrolments", "mdl_assign",
             "mdl_assign_submission", "mdl_grades", "mdl_logstore_standard_log",
             "campus_geo", "campus_capacity", "matricula_historica", "paper_catalog",
             "essay_submissions", "essay_rubric"}
faltan = esperadas - set(carpetas)
assert not faltan, f"Faltan datasets en landing: {faltan}"
print(f"✓ {len(carpetas)} datasets aterrizados en {LANDING}")
print(f"✓ {len(list(dbutils.fs.ls(DOCS)))} papers PDF · listos para el notebook 02 →")
display(spark.read.option("header", True).csv(f"{LANDING}/ps_personal_data").limit(5))
