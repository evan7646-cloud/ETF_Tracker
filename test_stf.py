import streamlit as st
import pandas as pd

df = pd.DataFrame({
    'col1': [':red[red text]', '<span style="color:red">html text</span>', 'normal text']
})

st.dataframe(df)

df_html = df.style.format({'col1': lambda x: f'<span style="color:red">{x}</span>' if 'normal' in x else x})
st.dataframe(df_html)
