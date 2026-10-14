# Sistema de APUs y Presupuestos

App en Streamlit para crear una biblioteca de insumos, armar Análisis de Precios
Unitarios (APU) por rubro, y generar presupuestos por proyecto. Multiusuario, con
roles: **admin**, **editor** (respaldo del admin) y **usuario**.

## 1. Crear el backend en Supabase (gratis)

1. Ve a [supabase.com](https://supabase.com) y crea una cuenta y un proyecto nuevo.
2. En el panel del proyecto, ve a **SQL Editor** → **New query**, pega todo el
   contenido de `schema.sql` de este repositorio y ejecútalo (▶ Run).
   Esto crea las tablas, la sincronización de usuarios y las políticas de seguridad.
3. Ve a **Authentication → Providers** y confirma que "Email" esté habilitado
   (viene activado por defecto). Si no quieres que los usuarios confirmen su
   correo antes de entrar, en **Authentication → Settings** desactiva
   "Confirm email".
4. Ve a **Project Settings → API** y copia:
   - **Project URL**
   - **anon public key**

## 2. Crear tu primer administrador

1. Abre la app (localmente o ya desplegada) y crea una cuenta desde la pestaña
   "Crear cuenta".
2. En Supabase, ve a **SQL Editor** y ejecuta (con tu correo real):
   ```sql
   update public.profiles set rol = 'admin' where email = 'tu_correo@ejemplo.com';
   ```
3. Desde ahí, ese usuario ya puede entrar a **Administración** para asignar
   roles (`editor` o `admin`) a los demás desde la interfaz, sin volver a tocar SQL.

## 3. Ejecutar localmente (opcional, para probar antes de desplegar)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edita .streamlit/secrets.toml con tu URL y anon_key de Supabase
streamlit run app.py
```

## 4. Desplegar en la nube (Streamlit Community Cloud, gratis)

1. Sube este proyecto a un repositorio de GitHub (público o privado).
   **No subas `.streamlit/secrets.toml`** (ya está en `.gitignore`); solo el
   archivo `.example` debe quedar en el repo.
2. Ve a [share.streamlit.io](https://share.streamlit.io) e inicia sesión con GitHub.
3. Clic en **New app**, selecciona el repositorio, rama y el archivo principal `app.py`.
4. En **Advanced settings → Secrets**, pega el contenido de tu
   `.streamlit/secrets.toml` real (con tus valores de Supabase).
5. Deploy. La app queda publicada en una URL tipo
   `https://tu-app.streamlit.app`, accesible para todo tu equipo.

## Roles

| Rol | Insumos / Rubros / APU | Proyectos que ve | Administrar roles |
|---|---|---|---|
| **admin** | Editar | Todos los del equipo | Sí |
| **editor** | Editar | Todos los del equipo | No |
| **usuario** | Solo lectura | Solo los propios | No |

## Estructura del proyecto

```
app.py                     # Login y menú principal
pages/
  1_Insumos.py              # Biblioteca de materiales, mano de obra, equipos
  2_Rubros_APU.py           # Composición y cálculo de cada APU
  3_Proyectos.py            # Crear/administrar proyectos
  4_Presupuesto.py          # Rubros + cantidades -> presupuesto por proyecto
  5_Administracion.py       # Asignar roles (solo admin)
utils/
  db.py                     # Cliente de conexión a Supabase
  auth.py                   # Login, registro, sesión, roles
  calculos.py               # Lógica de cálculo de APU y presupuesto
  exportar.py                # Exportación a Excel
schema.sql                  # Esquema completo de la base de datos (Supabase)
```

## Notas

- Los precios de insumos son **centralizados**: si un admin/editor actualiza un
  precio, automáticamente se refleja en el APU de todos los rubros que lo usan
  y en los presupuestos que dependen de esos rubros.
- El plan gratuito de Supabase y de Streamlit Community Cloud es suficiente
  para un equipo pequeño. Si el uso crece, se puede migrar el hosting a Render
  sin cambiar el código.
