import streamlit as st
from utils.auth import login, signup, logout, current_profile

st.set_page_config(page_title="Sistema de APUs y Presupuestos", page_icon="🏗️", layout="wide")


def pantalla_login():
    st.title("🏗️ Sistema de APUs y Presupuestos")
    tab_login, tab_signup = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Correo")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)
            if submitted:
                ok, msg = login(email, password)
                if ok:
                    st.rerun()
                else:
                    st.error(f"No se pudo iniciar sesión: {msg}")

    with tab_signup:
        with st.form("signup_form"):
            nombre = st.text_input("Nombre completo")
            email_s = st.text_input("Correo", key="signup_email")
            password_s = st.text_input("Contraseña", type="password", key="signup_pw")
            submitted_s = st.form_submit_button("Crear cuenta", use_container_width=True)
            if submitted_s:
                ok, msg = signup(email_s, password_s, nombre)
                if ok:
                    st.success(msg)
                else:
                    st.error(f"No se pudo crear la cuenta: {msg}")


def pantalla_principal():
    profile = current_profile()
    with st.sidebar:
        st.write(f"👤 **{profile.get('nombre') or profile.get('email')}**")
        st.caption(f"Rol: {profile.get('rol', 'usuario').capitalize()}")
        if st.button("Cerrar sesión", use_container_width=True):
            logout()
            st.rerun()

    st.title("🏗️ Sistema de APUs y Presupuestos")
    st.markdown(
        """
        Usa el menú de la izquierda para navegar:

        - **Insumos**: biblioteca de materiales, mano de obra y equipos con sus precios.
        - **Rubros / APU**: arma el Análisis de Precio Unitario de cada rubro a partir de los insumos.
        - **Proyectos**: crea y administra tus proyectos.
        - **Presupuesto**: selecciona rubros y cantidades para generar el presupuesto de cada proyecto.
        - **Cronograma** *(opcional)*: solo para los proyectos donde necesites planificar
          la ejecución del presupuesto en el tiempo (curva S).
        """
    )
    if profile.get("rol") == "admin":
        st.info("Como administrador, también tienes acceso a **Administración** para asignar roles al equipo.")
    elif profile.get("rol") == "editor":
        st.info("Como editor, puedes gestionar insumos, rubros/APU y ver todos los proyectos del equipo.")
    else:
        st.info(
            "Los precios de insumos y la biblioteca de rubros son administrados por un usuario "
            "administrador o editor. Tú puedes crear proyectos y armar presupuestos con lo disponible."
        )


if not st.session_state.get("auth_session"):
    pantalla_login()
else:
    pantalla_principal()
