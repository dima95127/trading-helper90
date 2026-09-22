import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window

import json
import urllib.request
import urllib.parse
import threading
import time
from datetime import datetime

Window.size = (400, 700)

# ============ INDICATORS (pure Python) ============

def sma(data, period):
    if len(data) < period:
        return []
    result = []
    for i in range(period - 1, len(data)):
        result.append(sum(data[i - period + 1: i + 1]) / period)
    return result

def ema(data, period):
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    result = []
    prev = sum(data[:period]) / period
    result.append(prev)
    for i in range(period, len(data)):
        prev = data[i] * k + prev * (1 - k)
        result.append(prev)
    return result

def rsi(data, period=14):
    if len(data) < period + 1:
        return []
    gains = []
    losses = []
    for i in range(1, len(data)):
        diff = data[i] - data[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result = []
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))
    return result

def macd(data, fast=12, slow=26, signal=9):
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    offset = slow - fast
    macd_line = []
    for i in range(len(ema_slow)):
        macd_line.append(ema_fast[i + offset] - ema_slow[i])
    signal_line = ema(macd_line, signal)
    histogram = []
    for i in range(len(signal_line)):
        histogram.append(macd_line[i + signal - 1] - signal_line[i])
    return macd_line, signal_line, histogram

def bollinger_bands(data, period=20, std_dev=2):
    if len(data) < period:
        return [], [], []
    upper = []
    lower = []
    middle = []
    for i in range(period - 1, len(data)):
        window = data[i - period + 1: i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = variance ** 0.5
        middle.append(mean)
        upper.append(mean + std_dev * sd)
        lower.append(mean - std_dev * sd)
    return upper, middle, lower

def stochastic(high, low, close, period=14):
    if len(close) < period:
        return []
    result = []
    for i in range(period - 1, len(close)):
        highest = max(high[i - period + 1: i + 1])
        lowest = min(low[i - period + 1: i + 1])
        if highest == lowest:
            result.append(50.0)
        else:
            result.append((close[i] - lowest) / (highest - lowest) * 100)
    return result

def williams_r(high, low, close, period=14):
    if len(close) < period:
        return []
    result = []
    for i in range(period - 1, len(close)):
        highest = max(high[i - period + 1: i + 1])
        lowest = min(low[i - period + 1: i + 1])
        if highest == lowest:
            result.append(-50.0)
        else:
            result.append((highest - close[i]) / (highest - lowest) * -100)
    return result

def adx(high, low, close, period=14):
    if len(close) < period * 2:
        return []
    tr_list = []
    plus_dm = []
    minus_dm = []
    for i in range(1, len(close)):
        tr = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        tr_list.append(tr)
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)
    atr = sum(tr_list[:period]) / period
    plus_di = 100 * (sum(plus_dm[:period]) / period) / atr if atr else 0
    minus_di = 100 * (sum(minus_dm[:period]) / period) / atr if atr else 0
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) else 0
    result = [dx]
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        plus_dm_val = (sum(plus_dm[i-period+1:i+1]) / period)
        minus_dm_val = (sum(minus_dm[i-period+1:i+1]) / period)
        plus_di = 100 * plus_dm_val / atr if atr else 0
        minus_di = 100 * minus_dm_val / atr if atr else 0
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) else 0
        result.append(dx)
    return result

# ============ DATA FETCHING ============

def fetch_binance_klines(symbol, interval, limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    opens = [float(c[1]) for c in data]
    highs = [float(c[2]) for c in data]
    lows = [float(c[3]) for c in data]
    closes = [float(c[4]) for c in data]
    volumes = [float(c[5]) for c in data]
    return opens, highs, lows, closes, volumes

def fetch_yahoo(symbol, interval='1d', range='3mo'):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    result = data['chart']['result'][0]
    quotes = result['indicators']['quote'][0]
    closes = [c for c in quotes['close'] if c is not None]
    highs = [c for c in quotes['high'] if c is not None]
    lows = [c for c in quotes['low'] if c is not None]
    volumes = [c for c in quotes['volume'] if c is not None]
    opens = [c for c in quotes['open'] if c is not None]
    return opens, highs, lows, closes, volumes

# ============ SIGNAL GENERATION ============

def generate_signal(opens, highs, lows, closes, volumes):
    signals = []
    if len(closes) < 30:
        return ["Not enough data"]
    
    rsi_val = rsi(closes, 14)
    macd_line, signal_line, histogram = macd(closes)
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes)
    stoch_val = stochastic(highs, lows, closes)
    wr_val = williams_r(highs, lows, closes)
    adx_val = adx(highs, lows, closes)
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    
    last_price = closes[-1]
    
    if rsi_val and rsi_val[-1] < 30:
        signals.append(f"RSI oversold: {rsi_val[-1]:.1f} -> BUY")
    elif rsi_val and rsi_val[-1] > 70:
        signals.append(f"RSI overbought: {rsi_val[-1]:.1f} -> SELL")
    else:
        signals.append(f"RSI neutral: {rsi_val[-1]:.1f}" if rsi_val else "RSI: N/A")
    
    if len(macd_line) > 1 and len(signal_line) > 0:
        if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2] if len(macd_line) > 1 else False:
            signals.append("MACD bullish crossover -> BUY")
        elif macd_line[-1] < signal_line[-1] and macd_line[-2] >= signal_line[-2] if len(macd_line) > 1 else False:
            signals.append("MACD bearish crossover -> SELL")
        else:
            signals.append(f"MACD: {'bullish' if macd_line[-1] > signal_line[-1] else 'bearish'}")
    
    if bb_upper and bb_lower:
        if last_price < bb_lower[-1]:
            signals.append("BB: price below lower band -> BUY")
        elif last_price > bb_upper[-1]:
            signals.append("BB: price above upper band -> SELL")
        else:
            signals.append("BB: price within bands")
    
    if stoch_val:
        if stoch_val[-1] < 20:
            signals.append(f"Stochastic oversold: {stoch_val[-1]:.1f} -> BUY")
        elif stoch_val[-1] > 80:
            signals.append(f"Stochastic overbought: {stoch_val[-1]:.1f} -> SELL")
        else:
            signals.append(f"Stochastic: {stoch_val[-1]:.1f}")
    
    if wr_val:
        if wr_val[-1] < -80:
            signals.append(f"Williams %R oversold: {wr_val[-1]:.1f} -> BUY")
        elif wr_val[-1] > -20:
            signals.append(f"Williams %R overbought: {wr_val[-1]:.1f} -> SELL")
        else:
            signals.append(f"Williams %R: {wr_val[-1]:.1f}")
    
    if adx_val and adx_val[-1] > 25:
        signals.append(f"ADX strong trend: {adx_val[-1]:.1f}")
    else:
        signals.append("ADX: weak/no trend")
    
    if ema9 and ema21:
        if ema9[-1] > ema21[-1]:
            signals.append("EMA9 > EMA21 -> bullish")
        else:
            signals.append("EMA9 < EMA21 -> bearish")
    
    buy_count = sum(1 for s in signals if 'BUY' in s)
    sell_count = sum(1 for s in signals if 'SELL' in s)
    
    if buy_count > sell_count:
        verdict = f"OVERALL: BUY ({buy_count} buy / {sell_count} sell)"
    elif sell_count > buy_count:
        verdict = f"OVERALL: SELL ({buy_count} buy / {sell_count} sell)"
    else:
        verdict = f"OVERALL: NEUTRAL ({buy_count} buy / {sell_count} sell)"
    
    signals.insert(0, verdict)
    return signals

# ============ MARTINGALE CALCULATOR ============

def martingale_calc(initial_amount, loss_percent, max_steps):
    results = []
    amount = initial_amount
    for step in range(1, max_steps + 1):
        results.append(f"Step {step}: {amount:.2f}")
        amount = amount / (1 - loss_percent / 100)
    return results

# ============ CHART WIDGET ============

class ChartWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.closes = []
        self.size_hint = (1, None)
        self.height = 250
        self.bind(size=self.draw_chart)
    
    def update_data(self, closes):
        self.closes = closes
        self.draw_chart()
    
    def draw_chart(self, *args):
        self.canvas.clear()
        if not self.closes or len(self.closes) < 2:
            return
        
        w = self.width
        h = self.height
        if w < 10 or h < 10:
            return
        
        min_val = min(self.closes)
        max_val = max(self.closes)
        if max_val == min_val:
            return
        
        margin = 10
        chart_w = w - 2 * margin
        chart_h = h - 2 * margin
        n = len(self.closes)
        
        with self.canvas:
            Color(0.15, 0.15, 0.18, 1)
            Rectangle(pos=(0, 0), size=(w, h))
            
            Color(0.3, 0.3, 0.35, 0.5)
            for i in range(5):
                y = margin + chart_h * i / 4
                Line(points=[margin, y, w - margin, y], width=0.5)
            
            Color(0.2, 0.8, 0.4, 1)
            points = []
            for i, c in enumerate(self.closes):
                x = margin + chart_w * i / (n - 1)
                y = margin + chart_h * (c - min_val) / (max_val - min_val)
                points.extend([x, y])
            
            if len(points) >= 4:
                Line(points=points, width=1.5)

# ============ MAIN APP ============

class TradingHelperApp(App):
    def build(self):
        self.title = 'Trading Helper'
        self.icon = 'icon.png'
        
        root = TabbedPanel()
        root.tab_pos = 'top'
        
        # ---- Tab 1: Signals ----
        tab_signals = TabbedPanelItem(text='Signals')
        signals_layout = BoxLayout(orientation='vertical', spacing=5, padding=10)
        
        controls = GridLayout(cols=2, size_hint=(1, None), height=120, spacing=5)
        
        self.source_spinner = Spinner(
            text='Binance',
            values=['Binance', 'Yahoo Finance'],
            size_hint=(1, None),
            height=44
        )
        
        self.pair_spinner = Spinner(
            text='BTCUSDT',
            values=['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                    'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
                    'MATICUSDT', 'ATOMUSDT', 'LTCUSDT', 'TRXUSDT'],
            size_hint=(1, None),
            height=44
        )
        
        self.tf_spinner = Spinner(
            text='1h',
            values=['15m', '30m', '1h', '4h', '1d', '1w'],
            size_hint=(1, None),
            height=44
        )
        
        analyze_btn = Button(
            text='Analyze',
            size_hint=(1, None),
            height=44,
            background_color=(0.2, 0.6, 0.3, 1)
        )
        analyze_btn.bind(on_press=self.on_analyze)
        
        controls.add_widget(self.source_spinner)
        controls.add_widget(self.pair_spinner)
        controls.add_widget(self.tf_spinner)
        controls.add_widget(analyze_btn)
        
        self.chart_widget = ChartWidget()
        
        scroll = ScrollView(size_hint=(1, 1))
        self.signals_label = Label(
            text='Press "Analyze" to get signals',
            size_hint_y=None,
            valign='top',
            halign='left',
            text_size=(None, None),
            color=(0.9, 0.9, 0.9, 1)
        )
        self.signals_label.bind(texture_size=self.signals_label.setter('size'))
        scroll.add_widget(self.signals_label)
        
        signals_layout.add_widget(controls)
        signals_layout.add_widget(self.chart_widget)
        signals_layout.add_widget(scroll)
        
        tab_signals.add_widget(signals_layout)
        root.add_widget(tab_signals)
        
        # ---- Tab 2: Martingale ----
        tab_mart = TabbedPanelItem(text='Martingale')
        mart_layout = BoxLayout(orientation='vertical', spacing=5, padding=10)
        
        mart_form = GridLayout(cols=2, size_hint=(1, None), height=120, spacing=5)
        
        mart_form.add_widget(Label(text='Initial amount:'))
        self.mart_amount = TextInput(text='100', multiline=False, input_filter='float')
        mart_form.add_widget(self.mart_amount)
        
        mart_form.add_widget(Label(text='Loss %:'))
        self.mart_loss = TextInput(text='90', multiline=False, input_filter='float')
        mart_form.add_widget(self.mart_loss)
        
        mart_form.add_widget(Label(text='Max steps:'))
        self.mart_steps = TextInput(text='5', multiline=False, input_filter='int')
        mart_form.add_widget(self.mart_steps)
        
        calc_btn = Button(text='Calculate', size_hint=(1, None), height=44,
                         background_color=(0.2, 0.6, 0.3, 1))
        calc_btn.bind(on_press=self.on_martingale)
        mart_form.add_widget(calc_btn)
        
        mart_scroll = ScrollView()
        self.mart_result = Label(
            text='Enter values and press Calculate',
            size_hint_y=None,
            valign='top',
            halign='left',
            color=(0.9, 0.9, 0.9, 1)
        )
        self.mart_result.bind(texture_size=self.mart_result.setter('size'))
        mart_scroll.add_widget(self.mart_result)
        
        mart_layout.add_widget(mart_form)
        mart_layout.add_widget(mart_scroll)
        
        tab_mart.add_widget(mart_layout)
        root.add_widget(tab_mart)
        
        # ---- Tab 3: Settings ----
        tab_settings = TabbedPanelItem(text='About')
        settings_layout = BoxLayout(orientation='vertical', spacing=10, padding=20)
        info = Label(
            text='Trading Helper v1.0\n\n'
                 'Signals: RSI, MACD, Bollinger Bands,\n'
                 'Stochastic, Williams %R, ADX, EMA\n\n'
                 'Sources: Binance API, Yahoo Finance\n\n'
                 'Martingale calculator included\n\n'
                 'Target: Android 12 (API 31)\n\n'
                 'Built with Kivy + pure Python',
            halign='center',
            valign='middle',
            color=(0.8, 0.8, 0.8, 1)
        )
        settings_layout.add_widget(info)
        tab_settings.add_widget(settings_layout)
        root.add_widget(tab_settings)
        
        return root
    
    def on_analyze(self, instance):
        self.signals_label.text = 'Loading...'
        self.chart_widget.closes = []
        self.chart_widget.draw_chart()
        
        thread = threading.Thread(target=self._fetch_and_analyze)
        thread.daemon = True
        thread.start()
    
    def _fetch_and_analyze(self):
        try:
            source = self.source_spinner.text
            pair = self.pair_spinner.text
            tf = self.tf_spinner.text
            
            if source == 'Binance':
                opens, highs, lows, closes, volumes = fetch_binance_klines(pair, tf, 100)
            else:
                yahoo_tf_map = {
                    '15m': '15m', '30m': '30m', '1h': '60m',
                    '4h': '60m', '1d': '1d', '1w': '1wk'
                }
                yahoo_range = {'15m': '1d', '30m': '1d', '1h': '5d',
                               '4h': '1mo', '1d': '3mo', '1w': '6mo'}
                ytf = yahoo_tf_map.get(tf, '1d')
                yrange = yahoo_range.get(tf, '3mo')
                opens, highs, lows, closes, volumes = fetch_yahoo(pair, ytf, yrange)
            
            signals = generate_signal(opens, highs, lows, closes, volumes)
            
            Clock.schedule_once(lambda dt: self._update_signals(signals, closes), 0)
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_error(str(e)), 0)
    
    def _update_signals(self, signals, closes):
        self.signals_label.text = '\n'.join(signals)
        self.chart_widget.update_data(closes[-50:])
    
    def _show_error(self, error):
        self.signals_label.text = f'Error: {error}'
    
    def on_martingale(self, instance):
        try:
            amount = float(self.mart_amount.text)
            loss = float(self.mart_loss.text)
            steps = int(self.mart_steps.text)
            if amount <= 0 or loss <= 0 or loss >= 100 or steps <= 0 or steps > 20:
                self.mart_result.text = 'Invalid input values'
                return
            results = martingale_calc(amount, loss, steps)
            total = sum(amount / (1 - loss / 100) ** i for i in range(steps))
            text = '\n'.join(results)
            text += f'\n\nTotal: {total:.2f}'
            self.mart_result.text = text
        except Exception as e:
            self.mart_result.text = f'Error: {e}'

if __name__ == '__main__':
    TradingHelperApp().run()
