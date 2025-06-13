        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{metric}</div>
                <div class="metric-value">{value}</div>
                <div style="font-size: 0.8rem; color: #a3a3a3; margin-top: 0.5rem;">
                    {desc}
                </div>
            </div>
            """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
