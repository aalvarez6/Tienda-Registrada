# ========== FUNCIONES DE DETECCIÓN Y EXTRACCIÓN ==========

def detect_file_type(file_path):
    suffix = Path(file_path).suffix.lower()
    
    if suffix == '.zip':
        if zipfile.is_zipfile(file_path):
            return "zip"
        return "unknown"
    
    if suffix == '.csv':
        try:
            pd.read_csv(file_path, nrows=1)
            return "csv"
        except:
            return "unknown"
    
    if suffix in ('.db', '.sqlite', '.sqlite3'):
        try:
            conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
            conn.close()
            return "sqlite"
        except:
            return "unknown"
    
    if suffix == '.dat':
        with open(file_path, 'rb') as f:
            header = f.read(20)
            if header.startswith(b'KF_DAT') or header.startswith(b'KFDATA'):
                return "kf_dat"
        return "kf_dat"   # asumir binario KF por defecto
    
    if suffix == '.bak':
        return "hiopos_bak"
    
    return "unknown"

def get_sqlite_tables(file_path):
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except:
        return []

def get_columns_from_table(file_path, table_name):
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns
    except:
        return []

def extract_max_id_from_sqlite(file_path, table_name, id_column):
    try:
        conn = sqlite3.connect(file_path)
        query = f"SELECT MAX({id_column}) FROM {table_name}"
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()[0]
        conn.close()
        return result if result is not None else 0
    except Exception as e:
        raise Exception(f"Error al leer {table_name}.{id_column}: {str(e)}")

def extract_max_id_from_kf_dat(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    HEADER_SIZE = 32
    RECORD_SIZE = 64
    if len(data) < HEADER_SIZE:
        raise Exception("Archivo KF.dat demasiado pequeño")
    offset = HEADER_SIZE
    ids = []
    while offset + RECORD_SIZE <= len(data):
        record = data[offset:offset+RECORD_SIZE]
        id_local = struct.unpack('<I', record[0:4])[0]
        ids.append(id_local)
        offset += RECORD_SIZE
    if not ids:
        raise Exception("No se encontraron registros en el archivo KF.dat")
    return max(ids)

def extract_max_id_from_hiopos_bak(file_path):
    # Intenta primero como SQLite (algunos .bak lo son)
    try:
        conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
        conn.close()
        raise Exception("El archivo .bak es SQLite. Usa modo manual en el sidebar para indicar tabla y columna ID.")
    except:
        pass
    # Si no, asumimos formato binario desconocido
    raise Exception("Formato .bak de HIOPOS no reconocido. Selecciona 'manual' en el sidebar y especifica tabla/columna (si es SQLite) o cambia a 'binario_kf' si es binario.")

def extract_max_local_id(file_path, file_type, pos_system, custom_table, custom_column):
    errors = []
    warnings = []
    max_id = 0

    try:
        if file_type == "sqlite":
            tables = get_sqlite_tables(file_path)
            if not tables:
                errors.append("La base SQLite no contiene tablas")
                return max_id, errors, warnings

            # Configuración de tabla/columna según sistema
            if pos_system == "hiopos":
                candidates = ['ventas', 'transacciones', 'Ventas', 'Transacciones']
                table_found = None
                for t in candidates:
                    if t in tables:
                        table_found = t
                        break
                if not table_found:
                    errors.append(f"No se encontró tabla de ventas. Tablas disponibles: {tables}")
                    return max_id, errors, warnings
                cols = get_columns_from_table(file_path, table_found)
                id_col = None
                for col in ['id_local', 'id', 'ID', 'id_venta']:
                    if col in cols:
                        id_col = col
                        break
                if not id_col:
                    errors.append(f"Columna ID no encontrada en {table_found}. Columnas: {cols}")
                    return max_id, errors, warnings
                max_id = extract_max_id_from_sqlite(file_path, table_found, id_col)

            elif pos_system == "kf":
                table_name = custom_table if custom_table else "Ventas"
                id_column = custom_column if custom_column else "Id"
                if table_name not in tables:
                    errors.append(f"Tabla '{table_name}' no encontrada. Tablas: {tables}")
                    return max_id, errors, warnings
                max_id = extract_max_id_from_sqlite(file_path, table_name, id_column)

            elif pos_system == "manual":
                if not custom_table or not custom_column:
                    errors.append("Para modo manual, debe especificar tabla y columna")
                    return max_id, errors, warnings
                if custom_table not in tables:
                    errors.append(f"Tabla '{custom_table}' no encontrada")
                    return max_id, errors, warnings
                max_id = extract_max_id_from_sqlite(file_path, custom_table, custom_column)
            else:
                errors.append(f"Sistema POS '{pos_system}' no soportado para SQLite")

        elif file_type == "kf_dat":
            if pos_system == "binario_kf" or pos_system == "kf":
                max_id = extract_max_id_from_kf_dat(file_path)
            else:
                errors.append(f"Archivo .dat detectado pero sistema POS no es 'binario_kf' o 'kf'. Cambia en el sidebar.")

        elif file_type == "hiopos_bak":
            if pos_system == "hiopos" or pos_system == "manual":
                max_id = extract_max_id_from_hiopos_bak(file_path)
            else:
                errors.append("Archivo .bak detectado. Selecciona 'hiopos' o 'manual' en el sidebar.")

        elif file_type == "zip":
            with zipfile.ZipFile(file_path, 'r') as zf:
                db_files = [f for f in zf.namelist() if f.endswith('.db')]
                if not db_files:
                    errors.append("El ZIP no contiene archivo .db")
                    return max_id, errors, warnings
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                    tmp.write(zf.read(db_files[0]))
                    tmp_path = tmp.name
                sub_max, sub_err, sub_warn = extract_max_local_id(tmp_path, "sqlite", pos_system, custom_table, custom_column)
                max_id = sub_max
                errors.extend(sub_err)
                warnings.extend(sub_warn)
                Path(tmp_path).unlink()

        elif file_type == "csv":
            df = pd.read_csv(file_path)
            id_col = custom_column if custom_column else 'id_local'
            if id_col not in df.columns:
                errors.append(f"CSV sin columna '{id_col}'")
                return max_id, errors, warnings
            max_id = df[id_col].max()

        else:
            errors.append("Tipo de archivo no soportado")

    except Exception as e:
        errors.append(f"Excepción: {str(e)}")

    return max_id, errors, warnings
