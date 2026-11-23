import sqlite3

conexion = sqlite3.connect("empresa.db")
cursor = conexion.cursor()
cursor.execute("PRAGMA foreign_keys = ON")   # activa las claves foráneas (SQLite las trae apagadas)

# ---------- 1. CREAR LAS TABLAS ----------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS empleados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        departamento TEXT NOT NULL,
        dias_vacaciones INTEGER NOT NULL DEFAULT 23
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS vacaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        dias INTEGER NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente',
        FOREIGN KEY (empleado_id) REFERENCES empleados(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER NOT NULL,
        titulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        prioridad TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'abierto',
        fecha TEXT NOT NULL,
        FOREIGN KEY (empleado_id) REFERENCES empleados(id)
    )
""")

# ---------- 2. DATOS DE EJEMPLO ----------
# Empleados (id 1 a 4)
cursor.execute("INSERT INTO empleados (nombre, departamento) VALUES (?, ?)", ("Lucía Gómez", "Desarrollo"))
cursor.execute("INSERT INTO empleados (nombre, departamento, dias_vacaciones) VALUES (?, ?, ?)", ("Pablo Serrano", "IT", 12))
cursor.execute("INSERT INTO empleados (nombre, departamento) VALUES (?, ?)", ("Elena Martín", "Finanzas"))
cursor.execute("INSERT INTO empleados (nombre, departamento) VALUES (?, ?)", ("Javier Ortega", "Comercial"))

# Vacaciones
cursor.execute(
    "INSERT INTO vacaciones (empleado_id, fecha_inicio, fecha_fin, dias, estado) VALUES (?, ?, ?, ?, ?)",
    (1, "2026-08-03", "2026-08-14", 10, "aprobada")
)
cursor.execute(
    "INSERT INTO vacaciones (empleado_id, fecha_inicio, fecha_fin, dias, estado) VALUES (?, ?, ?, ?, ?)",
    (1, "2026-12-28", "2026-12-31", 4, "pendiente")
)
cursor.execute(
    "INSERT INTO vacaciones (empleado_id, fecha_inicio, fecha_fin, dias, estado) VALUES (?, ?, ?, ?, ?)",
    (3, "2026-07-06", "2026-07-17", 10, "aprobada")
)

# Tickets
cursor.execute(
    "INSERT INTO tickets (empleado_id, titulo, descripcion, prioridad, estado, fecha) VALUES (?, ?, ?, ?, ?, ?)",
    (1, "No funciona la VPN", "Desde casa no consigo conectarme a la VPN, da error de autenticación.", "alta", "en curso", "2026-11-18")
)
cursor.execute(
    "INSERT INTO tickets (empleado_id, titulo, descripcion, prioridad, estado, fecha) VALUES (?, ?, ?, ?, ?, ?)",
    (4, "Instalar programa de diseño", "Necesito un programa para editar presentaciones de clientes.", "baja", "abierto", "2026-11-20")
)
cursor.execute(
    "INSERT INTO tickets (empleado_id, titulo, descripcion, prioridad, estado, fecha) VALUES (?, ?, ?, ?, ?, ?)",
    (3, "Pantalla externa parpadea", "La pantalla de la oficina parpadea cada pocos minutos.", "media", "resuelto", "2026-11-10")
)

# ---------- 3. GUARDAR Y CERRAR ----------
conexion.commit()
conexion.close()