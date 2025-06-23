# app_acomodo_abc.py - Versión Final Completa

import streamlit as st
from st_aggrid import AgGrid
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Configuración de página
st.set_page_config(layout="wide")

# Encabezado con logo y título en columnas
col1, col2 = st.columns([1, 5])
with col1:
    st.image('logo_taller.png', width=100)
with col2:
    st.title("📦 Acomodo Inteligente - Apilado por Tamaño de Caja")

# Sidebar: carga de archivo de plantilla Excel
with st.sidebar:
    archivo = st.file_uploader("📁 Cargar plantilla Excel", type=["xlsx"])

if archivo:
    # --- Carga y normalización de datos ---
    df_sku = pd.read_excel(archivo, sheet_name="SKU")
    df_ubic = pd.read_excel(archivo, sheet_name="Ubicaciones")

    df_sku = df_sku.rename(columns=lambda x: x.strip().lower().replace("  ", " "))
    df_sku = df_sku.rename(columns={'prioridad de orden': 'orden'})
    df_sku[['ancho caja', 'largo caja', 'alto caja']] = df_sku[['ancho caja', 'largo caja', 'alto caja']].astype(float)
    df_sku['total de cajas'] = pd.to_numeric(df_sku['total de cajas'], errors='coerce').fillna(0).astype(int)
    df_sku['volumen caja'] = df_sku['ancho caja'] * df_sku['largo caja'] * df_sku['alto caja']
    df_sku = df_sku.sort_values(by='orden')

    df_ubic['volumen'] = df_ubic['ancho'] * df_ubic['largo'] * df_ubic['alto']
    df_ubic['volumen disponible'] = df_ubic['volumen'] * 0.95
    df_ubic['ocupado'] = 0.0
    df_ubic['cajas'] = 0
    df_ubic['skus'] = 0

    # --- Simulación de acomodo ---
    asignaciones = []
    for _, sku in df_sku.iterrows():
        cajas_restantes = sku['total de cajas']
        volumen_caja = sku['volumen caja']
        for _, ubic in df_ubic.sort_values(by='id ubicacion').iterrows():
            if cajas_restantes <= 0:
                break
            espacio = ubic['volumen disponible'] - ubic['ocupado']
            max_por_vol = math.floor(espacio / volumen_caja)
            if max_por_vol <= 0:
                continue
            cajas_asignar = min(cajas_restantes, max_por_vol)
            volumen_asignado = cajas_asignar * volumen_caja

            # Actualizar estado de la ubicación
            df_ubic.loc[df_ubic['id ubicacion'] == ubic['id ubicacion'], 'ocupado'] += volumen_asignado
            df_ubic.loc[df_ubic['id ubicacion'] == ubic['id ubicacion'], 'cajas'] += cajas_asignar
            df_ubic.loc[df_ubic['id ubicacion'] == ubic['id ubicacion'], 'skus'] += 1

            # Registrar asignación
            asignaciones.append({
                'sku': sku['sku'],
                'ubicacion': ubic['id ubicacion'],
                'cajas asignadas': cajas_asignar,
                'volumen_asignado': volumen_asignado,
                'alto': sku['alto caja'],
                'ancho': sku['ancho caja'],
                'largo': sku['largo caja']
            })
            cajas_restantes -= cajas_asignar

    # --- Construcción de DataFrames de resultados ---
    df_asignacion = pd.DataFrame(asignaciones)

    # Mapa de volumen total por ubicación
    volumen_map = df_ubic.set_index('id ubicacion')['volumen']

    # Calcular % volumen SKU (volumen asignado / volumen ubicación)
    df_asignacion['% volumen SKU'] = (
        df_asignacion['volumen_asignado']
        / df_asignacion['ubicacion'].map(volumen_map)
        * 100
    ).round(2)

    # Resumen por ubicación: % volumen utilizado
    df_resumen = df_ubic[['id ubicacion', 'skus', 'cajas', 'ocupado', 'volumen']].copy()
    df_resumen['% volumen utilizado'] = (df_resumen['ocupado'] / df_resumen['volumen'] * 100).round(2)
    df_resumen = df_resumen.drop(columns=['ocupado', 'volumen'])

    # --- Mostrar tablas ---
    st.subheader("📋 Asignación de SKUs a Ubicaciones")
    AgGrid(
        df_asignacion[['sku', 'ubicacion', 'cajas asignadas', '% volumen SKU']],
        theme='material'
    )

    st.subheader("📊 Uso de Volumen por Ubicación")
    AgGrid(
        df_resumen.rename(columns={'% volumen utilizado': '% volumen ubicación'}),
        theme='material'
    )

    # --- Barra de estado global ---
    total_vol = df_ubic['volumen'].sum()
    total_ocupado = df_ubic['ocupado'].sum()
    pct_global = round((total_ocupado / total_vol) * 100, 2) if total_vol else 0
    color_global = '#f44336' if pct_global < 70 else '#ffeb3b' if pct_global < 90 else '#4CAF50'
    st.markdown("### Estado global de utilización del volumen")
    st.markdown(f"""
    <div style="background:#e0e0e0;border-radius:5px;padding:2px;width:100%">
      <div style="background:{color_global};width:{pct_global}%;padding:5px 0;border-radius:5px;color:{'black' if pct_global<90 else 'white'};text-align:center">
        {pct_global}% utilizado
      </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Simulación 3D por ubicación seleccionada ---
    ubic_list = df_resumen['id ubicacion'].tolist()
    sel = st.selectbox("📦 Ubicación para simulación 3D", ubic_list)
    if sel:
        data = df_ubic[df_ubic['id ubicacion'] == sel].iloc[0]
        ux, uy, uz = data['ancho'], data['largo'], data['alto']
        boxes = df_asignacion[df_asignacion['ubicacion'] == sel].copy()
        colores = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#17becf', '#8c564b', '#e377c2']
        boxes['color'] = [colores[i % len(colores)] for i in range(len(boxes))]
        boxes = boxes.sort_values(by='alto', ascending=False)

        fig = plt.figure(figsize=(8, 5))
        ax = fig.add_subplot(111, projection='3d')

        def draw_box(ax, x, y, z, dx, dy, dz, color):
            verts = [
                [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)],
                [(x, y, z), (x, y, z+dz), (x, y+dy, z+dz), (x, y+dy, z)],
                [(x, y, z), (x, y, z+dz), (x+dx, y, z+dz), (x+dx, y, z)],
                [(x+dx, y, z), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x+dx, y+dy, z)],
                [(x, y+dy, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
                [(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)]
            ]
            ax.add_collection3d(Poly3DCollection(verts, facecolors=color, linewidths=0.3, edgecolors='black', alpha=0.8))

        x0 = y0 = z0 = 0
        max_layer = 0
        leyenda = []
        for _, row in boxes.iterrows():
            dx, dy, dz = row['ancho'], row['largo'], row['alto']
            color = row['color']
            leyenda.append(f"{row['sku']} - {color}")
            for _ in range(int(row['cajas asignadas'])):
                if x0 + dx > ux:
                    x0 = 0
                    y0 += dy
                if y0 + dy > uy:
                    y0 = 0
                    z0 += max_layer
                    max_layer = 0
                if z0 + dz > uz:
                    break
                draw_box(ax, x0, y0, z0, dx, dy, dz, color)
                x0 += dx
                max_layer = max(max_layer, dz)

        ax.set_xlim(0, ux)
        ax.set_ylim(0, uy)
        ax.set_zlim(0, uz)
        ax.set_box_aspect([ux, uy, uz])
        ax.view_init(30, 135)
        st.pyplot(fig)

        # Barra de estado local
        pct_local = round(data['ocupado'] / data['volumen'] * 100, 2) if data['volumen'] else 0
        color_local = '#f44336' if pct_local < 70 else '#ffeb3b' if pct_local < 90 else '#4CAF50'
        st.markdown("### Estado de la ubicación seleccionada")
        st.markdown(f"""
        <div style="background:#e0e0e0;border-radius:5px;padding:2px;width:100%">
          <div style="background:{color_local};width:{pct_local}%;padding:5px 0;border-radius:5px;color:{'black' if pct_local<90 else 'white'};text-align:center">
            {pct_local}% utilizado
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Leyenda de colores
        st.markdown("### 🔖 Leyenda")
        for item in leyenda:
            sku_label, col = item.split(' - ')
            st.markdown(f"<span style='color:{col}'><b>■</b></span> {sku_label}", unsafe_allow_html=True)
