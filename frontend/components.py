"""
モダンUIコンポーネント集

再利用可能なUIコンポーネントとウィジェット
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


class ModernComponents:
    """モダンUIコンポーネント"""
    
    @staticmethod
    def render_live_price_card(symbol: str, price: float, change: float, 
                             volume: float = None, high_24h: float = None, 
                             low_24h: float = None):
        """ライブ価格カード"""
        change_color = "positive" if change >= 0 else "negative"
        change_symbol = "+" if change >= 0 else ""
        
        volume_text = f"Vol: {volume:,.0f}" if volume else ""
        range_text = f"Range: ¥{low_24h:,.0f} - ¥{high_24h:,.0f}" if high_24h and low_24h else ""
        
        return f"""
        <div class="metric-card">
            <div class="metric-label">{symbol}</div>
            <div class="metric-value">¥{price:,.0f}</div>
            <div class="{change_color}">{change_symbol}{change:.2f}%</div>
            <div style="font-size: 0.8rem; color: #a3a3a3; margin-top: 0.5rem;">
                {volume_text}<br>{range_text}
            </div>
        </div>
        """
    
    @staticmethod
    def render_position_card(symbol: str, side: str, size: float, 
                           entry_price: float, current_price: float,
                           pnl: float, pnl_pct: float):
        """ポジションカード"""
        side_color = "#00d4aa" if side == "LONG" else "#ff4757"
        pnl_color = "positive" if pnl >= 0 else "negative"
        
        return f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label">{symbol}</div>
                    <div style="color: {side_color}; font-weight: 600; margin: 0.25rem 0;">
                        {side} | {size}
                    </div>
                    <div style="font-size: 0.9rem; color: #a3a3a3;">
                        Entry: ¥{entry_price:,.0f}<br>
                        Current: ¥{current_price:,.0f}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div class="{pnl_color}" style="font-size: 1.2rem; font-weight: 600;">
                        ¥{pnl:,.0f}
                    </div>
                    <div class="{pnl_color}">
                        {pnl_pct:+.2f}%
                    </div>
                </div>
            </div>
        </div>
        """
    
    @staticmethod
    def render_strategy_status_card(name: str, status: str, 
                                  total_trades: int, win_rate: float,
                                  total_return: float, sharpe_ratio: float):
        """戦略ステータスカード"""
        status_colors = {
            "Active": "#00d4aa",
            "Testing": "#ff6b35",
            "Paused": "#a3a3a3",
            "Error": "#ff4757"
        }
        status_color = status_colors.get(status, "#a3a3a3")
        
        return f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #fafafa;">{name}</h4>
                    <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
                        <span style="color: #a3a3a3;">Trades: {total_trades}</span>
                        <span style="color: #a3a3a3;">Win: {win_rate:.1%}</span>
                        <span style="color: #a3a3a3;">Sharpe: {sharpe_ratio:.2f}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="color: {status_color}; font-size: 0.9rem; font-weight: 600;">
                        ● {status}
                    </div>
                    <div class="positive" style="font-size: 1.5rem; margin-top: 0.25rem;">
                        {total_return:+.1%}
                    </div>
                </div>
            </div>
        </div>
        """
    
    @staticmethod
    def create_candlestick_chart(df: pd.DataFrame, title: str = "Price Chart") -> go.Figure:
        """ローソク足チャート作成"""
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            increasing_line_color='#00d4aa',
            decreasing_line_color='#ff4757',
            increasing_fillcolor='rgba(0, 212, 170, 0.3)',
            decreasing_fillcolor='rgba(255, 71, 87, 0.3)'
        )])
        
        # ボリューム追加
        fig.add_trace(go.Bar(
            x=df.index,
            y=df['volume'],
            name='Volume',
            yaxis='y2',
            marker_color='rgba(255, 107, 53, 0.5)'
        ))
        
        fig.update_layout(
            title=title,
            template="plotly_dark",
            paper_bgcolor='rgba(26, 29, 36, 1)',
            plot_bgcolor='rgba(26, 29, 36, 1)',
            yaxis=dict(
                title="Price",
                titlefont=dict(color="#fafafa"),
                tickfont=dict(color="#a3a3a3"),
                gridcolor='rgba(45, 49, 57, 0.3)'
            ),
            yaxis2=dict(
                title="Volume",
                titlefont=dict(color="#fafafa"),
                tickfont=dict(color="#a3a3a3"),
                anchor="x",
                overlaying="y",
                side="right"
            ),
            xaxis=dict(
                rangeslider=dict(visible=False),
                tickfont=dict(color="#a3a3a3"),
                gridcolor='rgba(45, 49, 57, 0.3)'
            ),
            height=500
        )
        
        return fig
    
    @staticmethod
    def create_performance_gauge(value: float, title: str, 
                               min_value: float = -100, 
                               max_value: float = 100) -> go.Figure:
        """パフォーマンスゲージ"""
        # 色の決定
        if value > 30:
            bar_color = "#00d4aa"
        elif value > 0:
            bar_color = "#ff6b35"
        else:
            bar_color = "#ff4757"
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': title, 'font': {'color': '#fafafa'}},
            delta={'reference': 0},
            gauge={
                'axis': {
                    'range': [min_value, max_value],
                    'tickcolor': "#a3a3a3"
                },
                'bar': {'color': bar_color},
                'bgcolor': "#1a1d24",
                'borderwidth': 2,
                'bordercolor': "#2d3139",
                'steps': [
                    {'range': [min_value, 0], 'color': 'rgba(255, 71, 87, 0.1)'},
                    {'range': [0, max_value], 'color': 'rgba(0, 212, 170, 0.1)'}
                ],
                'threshold': {
                    'line': {'color': "#ff6b35", 'width': 4},
                    'thickness': 0.75,
                    'value': value
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(26, 29, 36, 1)',
            font={'color': "#fafafa"},
            height=250
        )
        
        return fig
    
    @staticmethod
    def create_portfolio_donut(allocations: Dict[str, float]) -> go.Figure:
        """ポートフォリオ円グラフ"""
        labels = list(allocations.keys())
        values = list(allocations.values())
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(
                colors=['#ff6b35', '#00d4aa', '#4ecdc4', '#45b7d1', '#5d76cb'],
                line=dict(color='#2d3139', width=2)
            ),
            textfont=dict(color='#fafafa'),
            textposition='outside'
        )])
        
        fig.update_layout(
            title="Portfolio Allocation",
            template="plotly_dark",
            paper_bgcolor='rgba(26, 29, 36, 1)',
            plot_bgcolor='rgba(26, 29, 36, 1)',
            showlegend=True,
            height=300,
            margin=dict(t=50, b=50, l=50, r=50)
        )
        
        return fig
    
    @staticmethod
    def render_alert_box(message: str, alert_type: str = "info"):
        """アラートボックス"""
        colors = {
            "success": {"bg": "rgba(0, 212, 170, 0.1)", "border": "#00d4aa", "icon": "✅"},
            "error": {"bg": "rgba(255, 71, 87, 0.1)", "border": "#ff4757", "icon": "❌"},
            "warning": {"bg": "rgba(255, 107, 53, 0.1)", "border": "#ff6b35", "icon": "⚠️"},
            "info": {"bg": "rgba(69, 183, 209, 0.1)", "border": "#45b7d1", "icon": "ℹ️"}
        }
        
        style = colors.get(alert_type, colors["info"])
        
        return f"""
        <div style="
            background-color: {style['bg']};
            border: 1px solid {style['border']};
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        ">
            <span style="font-size: 1.2rem;">{style['icon']}</span>
            <span style="color: #fafafa;">{message}</span>
        </div>
        """
    
    @staticmethod
    def create_mini_chart(data: List[float], color: str = "#00d4aa") -> go.Figure:
        """ミニスパークラインチャート"""
        fig = go.Figure(go.Scatter(
            y=data,
            mode='lines',
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)'
        ))
        
        fig.update_layout(
            showlegend=False,
            height=60,
            margin=dict(t=0, b=0, l=0, r=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False)
        )
        
        return fig
