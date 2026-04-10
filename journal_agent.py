# -*- coding: utf-8 -*-
"""
===================================
Model 5: 浜ゆ槗璁板綍鍛?(Trading Journal Agent)
===================================
鑱岃矗锛?1. 璁板綍姣忕瑪浜ゆ槗锛堜拱鍏?鍗栧嚭鏃堕棿銆佷环鏍笺€佷粨浣嶏級
2. 杩借釜鎸佷粨鐘舵€侊紙娴泩/娴簭锛?3. 璁＄畻姣忔棩/姣忓懆鐩堜簭缁熻
4. 姣忓懆鍏緭鍑哄鐩樻姤鍛婏紙鐩堝埄褰掑洜 / 浜忔崯褰掑洜 / 鏀硅繘寤鸿锛?5. 瀹氭湡鎺ㄩ€佷氦鏄撳懆鎶ョ粰鐢ㄦ埛
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import math

import anthropic
from dotenv import load_dotenv

from config import get_config

logger = logging.getLogger(__name__)


# ========== 浜ゆ槗璁板綍鏁版嵁妯″瀷 ==========

@dataclass
class Trade:
    """鍗曠瑪浜ゆ槗"""
    id: str
    code: str
    name: str
    action: str  # BUY / SELL
    price: float
    shares: int  # 鑲℃暟
    amount: float  # 鎴愪氦閲戦
    commission: float  # 鎵嬬画璐?    date: str  # 浜ゆ槗鏃ユ湡
    time: str  # 浜ゆ槗鏃堕棿
    stop_loss: float = 0.0  # 姝㈡崯浠?    take_profit_1: float = 0.0  # 绗竴姝㈢泩浠?    take_profit_2: float = 0.0  # 绗簩姝㈢泩浠?    reason: str = ""  # 涔板叆鐞嗙敱
    model4_reason: str = ""  # Model 4 鐨勬搷浣滅悊鐢?

@dataclass
class Position:
    """褰撳墠鎸佷粨"""
    code: str
    name: str
    shares: int
    avg_cost: float  # 鎸佷粨鎴愭湰
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    entry_date: str
    days_held: int = 0
    unrealized_pnl: float = 0.0  # 娴泩/浜?    unrealized_pnl_pct: float = 0.0


@dataclass
class DailyRecord:
    """姣忔棩璐︽埛蹇収"""
    date: str
    cash: float  # 鍙敤璧勯噾
    market_value: float  # 鎸佷粨甯傚€?    total_assets: float  # 鎬昏祫浜?    daily_pnl: float  # 褰撴棩鐩堜簭
    daily_pnl_pct: float  # 褰撴棩娑ㄨ穼骞?    positions: List[Position] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)


@dataclass
class WeeklyReport:
    """姣忓懆澶嶇洏鎶ュ憡"""
    week_start: str
    week_end: str
    week_pnl: float  # 鏈懆鐩堜簭
    week_pnl_pct: float  # 鏈懆娑ㄨ穼骞?    win_count: int  # 鐩堝埄娆℃暟
    loss_count: int  # 浜忔崯娆℃暟
    hold_count: int  # 鎸佷粨鏈钩浠?    total_trades: int  # 鎬讳氦鏄撴鏁?    win_rate: float  # 鑳滅巼
    avg_holding_days: float  # 骞冲潎鎸佷粨澶╂暟
    best_trade: Dict[str, Any] = {}  # 鏈€浣充氦鏄?    worst_trade: Dict[str, Any] = {}  # 鏈€宸氦鏄?    winners_analysis: str = ""  # 鐩堝埄鑲＄エ褰掑洜
    losers_analysis: str = ""  # 浜忔崯鑲＄エ褰掑洜
    improvements: List[str] = field(default_factory=list)  # 鏀硅繘寤鸿
    market_context: str = ""  # 鏈懆澶х洏鑳屾櫙


class JournalAgent:
    """
    Model 5: 浜ゆ槗璁板綍鍛?    
    璐熻矗锛?    - 璁板綍姣忕瑪浜ゆ槗鍒版湰鍦癑SON鏂囦欢
    - 杩借釜鎸佷粨鍜屾诞鐩堟诞浜?    - 姣忓懆鍏敓鎴愬鐩樻姤鍛?    - 鐢熸垚鍙鍖栫粺璁″浘琛紙鏂囧瓧鐗堬級
    """

    def __init__(self, data_dir: str = "./data/journal"):
        load_dotenv()
        config = get_config()
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.trades_file = self.data_dir / "trades.json"
        self.positions_file = self.data_dir / "positions.json"
        self.daily_file = self.data_dir / "daily_records.json"
        self.weekly_file = self.data_dir / "weekly_reports.json"
        
        self.account_size = 100000  # 妯℃嫙璐︽埛10涓囧厓
        
        # 鍒濆鍖栨枃浠?        self._init_files()

    def _init_files(self):
        """鍒濆鍖栨暟鎹枃浠?""
        if not self.trades_file.exists():
            self._save_json(self.trades_file, [])
        if not self.positions_file.exists():
            self._save_json(self.positions_file, [])
        if not self.daily_file.exists():
            self._save_json(self.daily_file, [])
        if not self.weekly_file.exists():
            self._save_json(self.weekly_file, [])

    def _load_json(self, path: Path) -> Any:
        """鍔犺浇JSON鏂囦欢"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save_json(self, path: Path, data: Any):
        """淇濆瓨JSON鏂囦欢"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def _new_id(self) -> str:
        """鐢熸垚鍞竴ID"""
        return f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000,9999)}"

    # ========== 浜ゆ槗璁板綍 ==========

    def record_buy(
        self,
        code: str,
        name: str,
        price: float,
        shares: int,
        stop_loss: float = 0,
        take_profit_1: float = 0,
        take_profit_2: float = 0,
        reason: str = "",
        model4_reason: str = "",
    ) -> Trade:
        """璁板綍涔板叆"""
        commission = round(price * shares * 0.0003, 2)  # 涓?浣ｉ噾
        trade = Trade(
            id=self._new_id(),
            code=code,
            name=name,
            action="BUY",
            price=price,
            shares=shares,
            amount=round(price * shares, 2),
            commission=commission,
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M:%S"),
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            reason=reason,
            model4_reason=model4_reason,
        )
        
        trades = self._load_json(self.trades_file)
        trades.append(asdict(trade))
        self._save_json(self.trades_file, trades)
        
        # 鏇存柊鎸佷粨
        self._update_position_on_buy(trade)
        
        logger.info(f"鉁?璁板綍涔板叆锛歿name}({code}) {shares}鑲?@{price:.2f}")
        return trade

    def record_sell(
        self,
        code: str,
        price: float,
        shares: Optional[int] = None,
        reason: str = "",
    ) -> Optional[Trade]:
        """璁板綍鍗栧嚭"""
        positions = self._load_json(self.positions_file)
        pos = next((p for p in positions if p['code'] == code), None)
        if not pos:
            logger.warning(f"鈿狅笍 鏈壘鍒版寔浠撹褰曪細{code}")
            return None
        
        sell_shares = shares or pos['shares']
        commission = round(price * sell_shares * 0.0003 + max(price * sell_shares * 0.001, 1), 2)  # 浣ｉ噾+鍗拌姳绋?        avg_cost = pos['avg_cost']
        
        pnl = (price - avg_cost) * sell_shares - commission
        pnl_pct = (price / avg_cost - 1) * 100
        
        trade = Trade(
            id=self._new_id(),
            code=code,
            name=pos['name'],
            action="SELL",
            price=price,
            shares=sell_shares,
            amount=round(price * sell_shares, 2),
            commission=commission,
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M:%S"),
            reason=reason,
            model4_reason=pos.get('model4_reason', ''),
        )
        
        trades = self._load_json(self.trades_file)
        trades.append(asdict(trade))
        self._save_json(self.trades_file, trades)
        
        # 鏇存柊鎸佷粨
        self._update_position_on_sell(code, sell_shares, price, avg_cost, commission)
        
        logger.info(f"鉁?璁板綍鍗栧嚭锛歿pos['name']}({code}) {sell_shares}鑲?@{price:.2f} | 鐩堜簭: {pnl:+.2f} ({pnl_pct:+.2f}%)")
        return trade

    def _update_position_on_buy(self, trade: Trade):
        """鏇存柊鎸佷粨锛堜拱鍏ュ悗锛?""
        positions = self._load_json(self.positions_file)
        existing = next((p for p in positions if p['code'] == trade.code), None)
        
        if existing:
            # 琛ヤ粨锛氶噸鏂拌绠楀潎浠?            total_cost = existing['avg_cost'] * existing['shares'] + trade.price * trade.shares
            total_shares = existing['shares'] + trade.shares
            existing['avg_cost'] = round(total_cost / total_shares, 4)
            existing['shares'] = total_shares
            existing['stop_loss'] = trade.stop_loss
            existing['take_profit_1'] = trade.take_profit_1
            existing['take_profit_2'] = trade.take_profit_2
        else:
            positions.append({
                'code': trade.code,
                'name': trade.name,
                'shares': trade.shares,
                'avg_cost': trade.price,
                'stop_loss': trade.stop_loss,
                'take_profit_1': trade.take_profit_1,
                'take_profit_2': trade.take_profit_2,
                'entry_date': trade.date,
                'days_held': 0,
                'model4_reason': trade.model4_reason,
            })
        
        self._save_json(self.positions_file, positions)

    def _update_position_on_sell(self, code: str, shares: int, price: float, avg_cost: float, commission: float):
        """鏇存柊鎸佷粨锛堝崠鍑哄悗锛?""
        positions = self._load_json(self.positions_file)
        pos = next((p for p in positions if p['code'] == code), None)
        
        if not pos:
            return
        
        remaining = pos['shares'] - shares
        if remaining <= 0:
            # 娓呬粨
            positions = [p for p in positions if p['code'] != code]
        else:
            pos['shares'] = remaining
            pos['avg_cost'] = avg_cost  # 鎴愭湰涓嶅彉
        
        self._save_json(self.positions_file, positions)

    def update_positions_price(self, current_prices: Dict[str, float]):
        """
        鏇存柊鎸佷粨鐨勫疄鏃朵环鏍煎拰娴泩浜?        
        Args:
            current_prices: {code: current_price}
        """
        positions = self._load_json(self.positions_file)
        today = datetime.now().strftime("%Y-%m-%d")
        
        for pos in positions:
            code = pos['code']
            if code not in current_prices:
                continue
            
            price = current_prices[code]
            pos['unrealized_pnl'] = round((price - pos['avg_cost']) * pos['shares'], 2)
            pos['unrealized_pnl_pct'] = round((price / pos['avg_cost'] - 1) * 100, 2)
            
            # 鏇存柊鎸佷粨澶╂暟
            entry = datetime.strptime(pos['entry_date'], "%Y-%m-%d")
            pos['days_held'] = (datetime.now() - entry).days
        
        self._save_json(self.positions_file, positions)
        return positions

    # ========== 缁熻鍒嗘瀽 ==========

    def get_open_positions(self) -> List[Position]:
        """鑾峰彇褰撳墠鎸佷粨"""
        data = self._load_json(self.positions_file)
        return [Position(**p) for p in data]

    def get_trade_history(self, days: int = 30) -> List[Trade]:
        """鑾峰彇浜ゆ槗鍘嗗彶"""
        trades = self._load_json(self.trades_file)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [Trade(**t) for t in trades if t['date'] >= cutoff]

    def get_weekly_stats(self, week_start: str, week_end: str) -> Dict[str, Any]:
        """鑾峰彇鏌愬懆鐨勭粺璁℃暟鎹?""
        trades = self._load_json(self.trades_file)
        week_trades = [Trade(**t) for t in trades 
                       if week_start <= t['date'] <= week_end and t['action'] == 'SELL']
        
        if not week_trades:
            return {
                'week_pnl': 0,
                'win_count': 0,
                'loss_count': 0,
                'total_trades': 0,
                'win_rate': 0,
                'avg_pnl_pct': 0,
            }
        
        total_pnl = sum(
            (t.price - t.amount / t.shares) * t.shares - t.commission
            for t in week_trades
        )
        
        wins = [t for t in week_trades if t['price'] * t['shares'] - t['amount'] > 0]
        losses = [t for t in week_trades if t['price'] * t['shares'] - t['amount'] <= 0]
        
        return {
            'week_pnl': round(total_pnl, 2),
            'win_count': len(wins),
            'loss_count': len(losses),
            'total_trades': len(week_trades),
            'win_rate': round(len(wins) / len(week_trades) * 100, 1),
            'avg_pnl_pct': round(
                sum((t.price / (t.amount / t.shares) - 1) * 100 for t in week_trades) / len(week_trades), 2
            ),
        }

    def generate_weekly_report(self) -> WeeklyReport:
        """鐢熸垚姣忓懆澶嶇洏鎶ュ憡锛堟瘡鍛ㄥ叚璋冪敤锛?""
        today = datetime.now()
        week_end = today.strftime("%Y-%m-%d")
        week_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        
        trades = self._load_json(self.trades_file)
        closed_trades = [Trade(**t) for t in trades 
                        if week_start <= t['date'] <= week_end and t['action'] == 'SELL']
        all_trades = [Trade(**t) for t in trades 
                      if week_start <= t['date'] <= week_end]
        
        positions = self._load_json(self.positions_file)
        
        # 璁＄畻鐩堜簭
        total_pnl = 0
        for t in closed_trades:
            cost = t.amount / t.shares
            pnl = (t.price - cost) * t.shares - t.commission
            total_pnl += pnl
        
        wins = []
        losses = []
        for t in closed_trades:
            cost = t.amount / t.shares
            pnl = (t.price - cost) * t.shares - t.commission
            pnl_pct = (t.price / cost - 1) * 100
            info = {"code": t.code, "name": t.name, "pnl": pnl, "pnl_pct": pnl_pct, "date": t.date}
            if pnl > 0:
                wins.append(info)
            else:
                losses.append(info)
        
        wins.sort(key=lambda x: x['pnl_pct'], reverse=True)
        losses.sort(key=lambda x: x['pnl_pct'])
        
        holding_days = []
        for t in all_trades:
            if t['action'] == 'BUY':
                entry = datetime.strptime(t['date'], "%Y-%m-%d")
                holding_days.append((today - entry).days)
        
        avg_days = sum(holding_days) / len(holding_days) if holding_days else 0
        
        report = WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            week_pnl=round(total_pnl, 2),
            week_pnl_pct=round(total_pnl / self.account_size * 100, 2),
            win_count=len(wins),
            loss_count=len(losses),
            hold_count=len(positions),
            total_trades=len(all_trades),
            win_rate=round(len(wins) / len(closed_trades) * 100, 1) if closed_trades else 0,
            avg_holding_days=round(avg_days, 1),
            best_trade=wins[0] if wins else {},
            worst_trade=losses[0] if losses else {},
        )
        
        return report

    def generate_ai_analysis(self, report: WeeklyReport) -> WeeklyReport:
        """鐢ˋI鐢熸垚褰掑洜鍒嗘瀽鍜屾敼杩涘缓璁?""
        config = get_config()
        api_key = config.gemini_api_key or config.openai_api_key
        
        if not api_key:
            report.winners_analysis = "鏈厤缃瓵PI锛屾棤娉曠敓鎴怉I鍒嗘瀽"
            report.losers_analysis = "鏈厤缃瓵PI锛屾棤娉曠敓鎴怉I鍒嗘瀽"
            return report
        
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""浣犳槸A鑲￠噺鍖栦氦鏄撳洟闃熺殑绛栫暐鍒嗘瀽甯堛€傝鏍规嵁鏈懆浜ゆ槗璁板綍杩涜澶嶇洏鍒嗘瀽锛?
浜ゆ槗缁熻锛?- 鏈懆鐩堜簭锛歿report.week_pnl:+.2f}鍏冿紙{report.week_pnl_pct:+.2f}%锛?- 鐩堝埄娆℃暟锛歿report.win_count} | 浜忔崯娆℃暟锛歿report.loss_count} | 鎸佷粨涓細{report.hold_count}绗?- 鑳滅巼锛歿report.win_rate}%
- 骞冲潎鎸佷粨澶╂暟锛歿report.avg_holding_days}澶?- 鏈€浣充氦鏄擄細{report.best_trade.get('name','N/A')}({report.best_trade.get('code','N/A')}) {report.best_trade.get('pnl_pct',0):+.2f}%
- 鏈€宸氦鏄擄細{report.worst_trade.get('name','N/A')}({report.worst_trade.get('code','N/A')}) {report.worst_trade.get('pnl_pct',0):+.2f}%

璇峰垎鏋愶細
1. 鐩堝埄鑲＄エ鐨勫叡鍚岀壒鐐规槸浠€涔堬紵锛堥€夎偂閫昏緫/鍏ュ満鏃舵満/鏉垮潡閫夋嫨锛?2. 浜忔崯鑲＄エ鐨勫け璇湪鍝噷锛燂紙鍒ゆ柇閿欒/杩介珮/姝㈡崯涓嶅強鏃?鏉垮潡杞姩锛燂級
3. 涓嬪懆鎿嶄綔鏀硅繘寤鸿锛?-5鏉★級

璇风敤JSON鏍煎紡杈撳嚭锛?{{
  "winners_analysis": "鐩堝埄褰掑洜鍒嗘瀽锛?00瀛椾互鍐咃級",
  "losers_analysis": "浜忔崯褰掑洜鍒嗘瀽锛?00瀛椾互鍐咃級",
  "improvements": ["鏀硅繘寤鸿1", "鏀硅繘寤鸿2", "鏀硅繘寤鸿3"]
}}"""
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            
            if "```json" in raw:
                start = raw.find("```json") + 7
                end = raw.rfind("```")
                raw = raw[start:end].strip()
            
            data = json.loads(raw)
            report.winners_analysis = data.get('winners_analysis', '')
            report.losers_analysis = data.get('losers_analysis', '')
            report.improvements = data.get('improvements', [])
            
        except Exception as e:
            logger.warning(f"AI鍒嗘瀽鐢熸垚澶辫触: {e}")
        
        return report

    # ========== 鏍煎紡鍖栬緭鍑?==========

    def format_position_report(self) -> str:
        """鏍煎紡鍖栨寔浠撴姤鍛?""
        positions = self.get_open_positions()
        if not positions:
            return "馃摥 **褰撳墠鏃犳寔浠?*"
        
        lines = [
            f"馃搳 **鎸佷粨鎶ュ憡** | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
        ]
        
        total_value = 0
        total_cost = 0
        
        for p in positions:
            value = p.avg_cost * p.shares
            total_cost += value
            lines.extend([
                f"**{p.name}锛坽p.code}锛?*",
                f"  鎸佽偂锛歿p.shares}鑲?| 鎴愭湰锛歿p.avg_cost:.2f}",
                f"  娴泩锛歿p.unrealized_pnl:+.2f}鍏冿紙{p.unrealized_pnl_pct:+.2f}%锛?,
                f"  鎸佷粨锛歿p.days_held}澶?| 姝㈡崯锛歿p.stop_loss:.2f} | 姝㈢泩1锛歿p.take_profit_1:.2f}",
                f"",
            ])
        
        return "\n".join(lines)

    def format_weekly_report(self, report: WeeklyReport) -> str:
        """鏍煎紡鍖栨瘡鍛ㄥ鐩樻姤鍛婏紙椋炰功鎺ㄩ€侊級"""
        pnl_emoji = "馃煝" if report.week_pnl >= 0 else "馃敶"
        
        lines = [
            f"馃搵 **姣忓懆浜ゆ槗澶嶇洏鎶ュ憡**",
            f"{report.week_start} 锝?{report.week_end}",
            f"",
            f"**{'-'*32}**",
            f"馃挵 **鏈懆鐩堜簭姹囨€?*",
            f"  {pnl_emoji} 鎬荤泩浜忥細{report.week_pnl:+.2f}鍏冿紙{report.week_pnl_pct:+.2f}%锛?,
            f"  馃搱 鐩堝埄锛歿report.win_count}绗?| 馃搲 浜忔崯锛歿report.loss_count}绗?| 鈴革笍 鎸佷粨涓細{report.hold_count}绗?,
            f"  馃幆 鑳滅巼锛歿report.win_rate}%",
            f"  鈴憋笍 骞冲潎鎸佷粨锛歿report.avg_holding_days}澶?,
            f"",
            f"**{'-'*32}**",
            f"馃弳 **鏈€浣充氦鏄?*",
        ]
        
        if report.best_trade:
            lines.append(f"  {report.best_trade['name']}({report.best_trade['code']}) {report.best_trade['pnl_pct']:+.2f}%")
        else:
            lines.append("  鏈懆鏃犲钩浠撲氦鏄?)
        
        lines.extend([
            f"",
            f"馃挃 **鏈€宸氦鏄?*",
        ])
        
        if report.worst_trade:
            lines.append(f"  {report.worst_trade['name']}({report.worst_trade['code']}) {report.worst_trade['pnl_pct']:+.2f}%")
        else:
            lines.append("  鏈懆鏃犲钩浠撲氦鏄?)
        
        lines.extend([
            f"",
            f"**{'-'*32}**",
            f"馃 **AI 褰掑洜鍒嗘瀽**",
            f"",
            f"鉁?**鐩堝埄褰掑洜**锛歿report.winners_analysis}",
            f"",
            f"鉂?**浜忔崯褰掑洜**锛歿report.losers_analysis}",
            f"",
            f"**{'-'*32}**",
            f"馃摑 **涓嬪懆鏀硅繘寤鸿**",
        ])
        
        for i, imp in enumerate(report.improvements, 1):
            lines.append(f"  {i}. {imp}")
        
        lines.extend([
            f"",
            f"**{'-'*32}**",
            f"鈿狅笍 妯℃嫙鐩樿褰曪紝浠呬緵鍒嗘瀽鎬荤粨锛岃偂甯傛湁椋庨櫓",
            f"",
            f"鈥斺€?Model 5 | 浜ゆ槗璁板綍鍛?,
        ])
        
        return "\n".join(lines)

    def to_json(self, report: WeeklyReport) -> str:
        """瀵煎嚭JSON鏍煎紡"""
        data = asdict(report)
        return json.dumps(data, ensure_ascii=False, indent=2)


# ========== 蹇嵎璋冪敤鍏ュ彛 ==========

def record_buy(
    code: str, name: str, price: float, shares: int,
    stop_loss: float = 0, take_profit_1: float = 0, take_profit_2: float = 0,
    reason: str = "", model4_reason: str = ""
):
    """蹇嵎涔板叆璁板綍"""
    agent = JournalAgent()
    return agent.record_buy(code, name, price, shares, stop_loss, take_profit_1, take_profit_2, reason, model4_reason)


def record_sell(code: str, price: float, shares: int = None, reason: str = ""):
    """蹇嵎鍗栧嚭璁板綍"""
    agent = JournalAgent()
    return agent.record_sell(code, price, shares, reason)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    agent = JournalAgent()
    
    # 娴嬭瘯锛氱敓鎴愬懆鎶?    report = agent.generate_weekly_report()
    report = agent.generate_ai_analysis(report)
    print(agent.format_weekly_report(report))
