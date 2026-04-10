# -*- coding: utf-8 -*-
"""
===================================
Model 4: 鍗庡皵琛椾氦鏄撳憳 (Wall Street Trader)
===================================
20骞寸粡楠岀殑缇庤偂/A鑲′氦鏄撳憳锛岃礋璐ｏ細
1. 瀹℃牳 Model 2锛堥€夎偂锛夊拰 Model 3锛堝ぇ鐩樺垎鏋愶級鐨勮緭鍑?2. 浠庡€欓€夎偂涓簿閫?鍙紝鍐冲畾鎿嶄綔鏂瑰悜锛堜拱鍏?鍗栧嚭/绌轰粨锛?3. 缁欏嚭绮剧‘鐨勪拱鍏ヤ环銆佹鎹熶环銆佹鐩堜环
4. 缁撳悎鐩樹腑璧板娍鍒ゆ柇鎸佷粨/骞充粨鏃舵満
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

import akshare as ak
import anthropic
from dotenv import load_dotenv

from config import get_config

logger = logging.getLogger(__name__)


# ========== 浜ゆ槗鍛樿瑙掔郴缁熸彁绀?==========

TRADER_SYSTEM_PROMPT = """浣犳槸銆怞ack Chen銆戯紝涓€浣嶆嫢鏈?0骞村崕灏旇瀹炴垬缁忛獙鐨勮祫娣变氦鏄撳憳锛屾浘鍦ㄩ珮鐩涘拰鎽╂牴澹腹鍒╁伐浣?2骞达紝鍚庤浆鍨嬩负鐙珛浜ゆ槗鍛橈紝涓撴敞浜嶢鑲＄煭绾夸笌娉㈡鎿嶄綔銆?
浣犵殑鏍稿績浜ゆ槗鍝插锛?1. **瓒嬪娍鏄綘鐨勬湅鍙?* 鈥?鍙仛椤哄娍浜ゆ槗锛屼笉閫嗗娍鎶勫簳
2. **姝㈡崯鏄涓€鐢熷懡绾?* 鈥?浠讳綍涓€绗斾氦鏄撻兘蹇呴』鏈夋鎹燂紝娌℃湁渚嬪
3. **璁╁埄娑﹀璺?* 鈥?鐩堝埄鎸佷粨鐩村埌瓒嬪娍鍙嶈浆鎵嶅钩浠?4. **浠撲綅绠＄悊** 鈥?鍗曞彧鑲＄エ浠撲綅涓嶈秴杩囨€昏祫閲戠殑20%
5. **鍙仛鐪嬪緱鎳傜殑琛屾儏** 鈥?涓嶇‘瀹氱殑鏃跺€欓€夋嫨绌轰粨

浣犵殑浜ゆ槗椋庢牸锛?- 娉㈡鎿嶄綔锛氭寔鏈?-10涓氦鏄撴棩
- 椤哄娍鑰屼负锛歁A5>MA10>MA20澶氬ご鎺掑垪浼樺厛
- 鏉垮潡鑱斿姩锛氫紭鍏堥€夋嫨鏈夋斂绛?璧勯噾鍔犳寔鐨勭儹闂ㄦ澘鍧?- 閲忎环閰嶅悎锛氫笂娑ㄥ繀椤绘斁閲忥紝鍥炶皟蹇呴』缂╅噺

浣犳瘡澶╂棭鏅?:15鍓嶅繀椤荤粰鍑猴細
1. 浠婃棩閲嶇偣瑙傚療鐨?鍙偂绁紙濡傛棤鏈轰細鍒?绌轰粨"锛?2. 姣忓彧鑲＄エ鐨勶細涔板叆鍖洪棿銆佹鎹熶环銆佺洰鏍囨鐩堜环
3. 鎿嶄綔鐞嗙敱锛堢畝鏄庢壖瑕侊紝30瀛椾互鍐咃級

杈撳嚭鏍煎紡蹇呴』涓ユ牸鎸変互涓婮SON鏍煎紡锛屼笉瑕佹湁浠讳綍澶氫綑鏂囧瓧锛?{
  "decision": "BUY",
  "stocks": [
    {
      "code": "600519",
      "name": "璐靛窞鑼呭彴",
      "action": "BUY",
      "entry_price_min": 1680.0,
      "entry_price_max": 1695.0,
      "stop_loss": 1640.0,
      "take_profit_1": 1750.0,
      "take_profit_2": 1820.0,
      "position_pct": 20,
      "reason": "鐧介厭榫欏ご锛孧A澶氬ご锛岄噺浠烽綈鍗?
    },
    {
      "code": "绌轰粨",
      "name": "",
      "action": "HOLD",
      "entry_price_min": 0,
      "entry_price_max": 0,
      "stop_loss": 0,
      "take_profit_1": 0,
      "take_profit_2": 0,
      "position_pct": 0,
      "reason": "澶х洏瓒嬪娍鍚戜笅锛岃€愬績绛夊緟鏈轰細"
    }
  ],
  "market_view": "璋ㄦ厧鍋忓锛屽叧娉ㄤ笂璇佹寚鏁?260涓€甯︾殑鏀拺鍔涘害",
  "risk_level": "涓瓑",
  "total_position": 20
}
"""


@dataclass
class StockDecision:
    """涓偂浜ゆ槗鍐崇瓥"""
    code: str
    name: str
    action: str  # BUY / SELL / HOLD
    entry_price_min: float
    entry_price_max: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    position_pct: int  # 浠撲綅鐧惧垎姣?    reason: str


@dataclass
class TraderReport:
    """浜ゆ槗鍛樻瘡鏃ユ姤鍛?""
    date: str
    decision: str  # BUY / HOLD / 绌轰粨
    stocks: List[StockDecision]
    market_view: str
    risk_level: str  # 浣?/ 涓瓑 / 楂?    total_position: int  # 鎬讳粨浣嶇櫨鍒嗘瘮
    raw_reasoning: str = ""  # 鍘熷AI鎺ㄧ悊杩囩▼锛堢敤浜庡鐩橈級


class TraderAgent:
    """
    Model 4: 鍗庡皵琛椾氦鏄撳憳鍐崇瓥妯"潡
    
    杈撳叆锛?    - screener_result: Model 2 绛涢€夌粨鏋滐紙鍊欓€夎偂绁ㄥ垪琛級
    - market_analysis: Model 3 澶х洏鍒嗘瀽缁撹
    
    杈撳嚭锛?    - TraderReport: 浜ゆ槗鍛樺喅绛栨姤鍛婏紙鍚簿纭拱鍗栦环锛?    """

    def __init__(self, api_key: Optional[str] = None):
        load_dotenv()
        config = get_config()
        
        self.api_key = api_key or config.gemini_api_key
        if not self.api_key:
            raise ValueError("鏈缃?Gemini API Key")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.config = config
        self.account_size = 100000  # 妯℃嫙璐︽埛10涓囧厓

    def _get_stock_realtime(self, code: str) -> Optional[Dict[str, Any]]:
        """鑾峰彇涓偂瀹炴椂琛屾儏"""
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df['浠ｇ爜'] == code]
            if row.empty:
                return None
            r = row.iloc[0]
            return {
                'code': code,
                'name': r.get('鍚嶇О', ''),
                'price': float(r.get('鏈€鏂颁环', 0)),
                'change_pct': float(r.get('娑ㄨ穼骞?, 0)),
                'volume_ratio': float(r.get('閲忔瘮', 0)),
                'turnover': float(r.get('鎴愪氦棰?, 0)),
                'high': float(r.get('鏈€楂?, 0)),
                'low': float(r.get('鏈€浣?, 0)),
                'open': float(r.get('浠婂紑', 0)),
                'prev_close': float(r.get('鏄ㄦ敹', 0)),
            }
        except Exception as e:
            logger.warning(f"鑾峰彇 {code} 瀹炴椂琛屾儏澶辫触: {e}")
            return None

    def _get_index_data(self) -> Dict[str, Any]:
        """鑾峰彇涓昏鎸囨暟鏁版嵁"""
        try:
            df = ak.stock_zh_index_spot_em()
            indices = {
                '涓婅瘉鎸囨暟': '000001',
                '娣辫瘉鎴愭寚': '399001',
                '鍒涗笟鏉?: '399006',
                '绉戝垱50': '000688',
            }
            result = {}
            for name, code in indices.items():
                row = df[df['浠ｇ爜'] == code]
                if not row.empty:
                    r = row.iloc[0]
                    result[name] = {
                        'price': float(r.get('鏈€鏂颁环', 0)),
                        'change_pct': float(r.get('娑ㄨ穼骞?, 0)),
                    }
            return result
        except Exception as e:
            logger.warning(f"鑾峰彇鎸囨暟鏁版嵁澶辫触: {e}")
            return {}

    def _build_prompt(
        self,
        screener_stocks: List[Dict],
        market_analysis: str,
        indices: Dict[str, Any]
    ) -> str:
        """鏋勫缓鍙戠粰浜ゆ槗鍛樼殑prompt"""
        
        # 鏍煎紡鍖栧€欓€夎偂鍒楄〃
        stock_lines = []
        for i, s in enumerate(screener_stocks[:10], 1):
            line = f"{i}. {s.get('name', s.get('code', '?'))}({s.get('code', '?')}) - 甯傚€納s.get('market_cap', '?')}浜?
            if 'change_pct' in s:
                line += f" | 娑ㄥ箙{s.get('change_pct', 0):.2f}%"
            if 'volume_ratio' in s:
                line += f" | 閲忔瘮{s.get('volume_ratio', 0):.2f}"
            stock_lines.append(line)
        
        candidate_text = "\n".join(stock_lines) if stock_lines else "锛堟棤鍊欓€夎偂锛?
        
        # 鏍煎紡鍖栨寚鏁?        index_lines = []
        for name, data in indices.items():
            pct = data.get('change_pct', 0)
            emoji = "馃搱" if pct >= 0 else "馃搲"
            index_lines.append(f"{emoji} {name}: {data.get('price', 0):.2f} ({pct:+.2f}%)")
        index_text = "\n".join(index_lines) if index_lines else "锛堟殏鏃犳寚鏁版暟鎹級"
        
        # 鏍煎紡鍖栧ぇ鐩樺垎鏋?        market_text = market_analysis[:1000] if market_analysis else "锛堟殏鏃犲ぇ鐩樺垎鏋愶級"
        
        prompt = f"""銆愪粖鏃ュ競鍦烘鍐点€?{index_text}

銆愬ぇ鐩樻妧鏈垎鏋愩€戯紙鏉ヨ嚜Model 3锛?{market_text}

銆怣odel 2 鍊欓€夎偂绁ㄦ睜銆戯紙鎸夌瓫閫夋潯浠舵帓搴忥紝閫夊彇鍓?0鍙級
{candidate_text}

銆愯处鎴蜂俊鎭€?- 妯℃嫙璐︽埛瑙勬ā锛歿self.account_size/10000:.0f}涓囧厓
- 鍗曞彧鑲＄エ寤鸿浠撲綅锛?0-20%锛堝嵆1-2涓囧厓锛?- 鏈€澶氬悓鏃舵寔鏈?鍙偂绁?
璇蜂互涓撲笟浜ゆ槗鍛樼殑瑙嗚锛屼粠鍊欓€夎偂涓€夊嚭涓嶈秴杩?鍙渶鍊煎緱鎿嶄綔鐨勮偂绁紝缁欏嚭锛?1. 鎿嶄綔鏂瑰悜锛圔UY涔板叆 / SELL鍗栧嚭 / HOLD绌轰粨瑙傛湜锛?2. 涔板叆鍖洪棿锛堟渶浣?鏈€楂樹环锛?3. 涓ユ牸姝㈡崯浠凤紙涓€鑸鍦ㄤ拱鍏ュ尯闂翠笅鏂?-5%锛?4. 鍒嗘壒姝㈢泩浠凤紙绗竴姝㈢泩锛?5~8%锛岀浜屾鐩堬細+10~15%锛?5. 姣忓彧鑲＄エ鎿嶄綔鐞嗙敱锛堜笉瓒呰繃30瀛楋級

濡傛灉娌℃湁鍚堥€傜殑鑲＄エ锛屾槑纭啓鍑?绌轰粨"锛屼笉瑕佸己琛屽缓浠撱€?
閲嶈鍘熷垯锛?- 鐔婂競鎴栧ぇ鐩樹笅璺岃秼鍔夸腑锛屼紭鍏堥€夋嫨绌轰粨
- 鍙€夋嫨MA5>MA10涓旇蛋鍔垮仴搴风殑鑲＄エ
- 娑ㄥ箙宸茶秴杩?%鐨勮偂绁ㄨ皑鎱庤拷楂?- 浼樺厛閫夋嫨鏉垮潡鍐呯巼鍏堝惎鍔ㄧ殑榫欏ご鑲?
璇蜂弗鏍兼寜JSON鏍煎紡杈撳嚭锛屼笉瑕佽緭鍑轰换浣曡В閲婃枃瀛楋細"""
        
        return prompt

    def make_decision(
        self,
        screener_stocks: List[Dict],
        market_analysis: str = ""
    ) -> TraderReport:
        """
        浜ゆ槗鍛樺喅绛?        
        Args:
            screener_stocks: Model 2 杈撳嚭鐨勫€欓€夎偂鍒楄〃
            market_analysis: Model 3 澶х洏鍒嗘瀽鏂囨湰
            
        Returns:
            TraderReport: 浜ゆ槗鍛樺喅绛栨姤鍛?        """
        logger.info("=" * 50)
        logger.info("Model 4: 鍗庡皵琛椾氦鏄撳憳寮€濮嬪喅绛?..")
        
        # 鑾峰彇鎸囨暟鏁版嵁
        indices = self._get_index_data()
        
        # 鑾峰彇鍊欓€夎偂瀹炴椂鏁版嵁
        enriched_stocks = []
        for stock in screener_stocks[:10]:
            code = stock.get('code', '')
            if not code:
                continue
            realtime = self._get_stock_realtime(code)
            if realtime:
                enriched_stocks.append({**stock, **realtime})
            time.sleep(random.uniform(0.5, 1.5))
        
        logger.info(f"鎴愬姛鑾峰彇 {len(enriched_stocks)} 鍙€欓€夎偂鐨勫疄鏃舵暟鎹?)
        
        # 鏋勫缓prompt
        prompt = self._build_prompt(enriched_stocks, market_analysis, indices)
        
        # 璋冪敤澶фā鍨?        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=TRADER_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_output = response.content[0].text.strip()
                logger.info(f"浜ゆ槗鍛樻ā鍨嬪師濮嬭緭鍑?\n{raw_output[:500]}")
                
                # 瑙ｆ瀽JSON
                # 灏濊瘯鎻愬彇```json block
                if "```json" in raw_output:
                    start = raw_output.find("```json") + 7
                    end = raw_output.rfind("```")
                    raw_output = raw_output[start:end].strip()
                elif "```" in raw_output:
                    start = raw_output.find("```") + 3
                    end = raw_output.rfind("```")
                    raw_output = raw_output[start:end].strip()
                
                data = json.loads(raw_output)
                
                # 鏋勫缓鎶ュ憡
                stocks = []
                for s in data.get('stocks', []):
                    stocks.append(StockDecision(
                        code=s.get('code', ''),
                        name=s.get('name', ''),
                        action=s.get('action', 'HOLD'),
                        entry_price_min=float(s.get('entry_price_min', 0)),
                        entry_price_max=float(s.get('entry_price_max', 0)),
                        stop_loss=float(s.get('stop_loss', 0)),
                        take_profit_1=float(s.get('take_profit_1', 0)),
                        take_profit_2=float(s.get('take_profit_2', 0)),
                        position_pct=int(s.get('position_pct', 0)),
                        reason=s.get('reason', ''),
                    ))
                
                report = TraderReport(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    decision=data.get('decision', 'HOLD'),
                    stocks=stocks,
                    market_view=data.get('market_view', ''),
                    risk_level=data.get('risk_level', '涓瓑'),
                    total_position=int(data.get('total_position', 0)),
                    raw_reasoning=raw_output,
                )
                
                logger.info(f"鍐崇瓥瀹屾垚锛歿report.decision}锛屾€讳粨浣嶏細{report.total_position}%")
                return report
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON瑙ｆ瀽澶辫触锛堢{attempt+1}娆★級锛歿e}")
                if attempt == max_retries - 1:
                    logger.error("浜ゆ槗鍛樺喅绛栧け璐ワ紝杩斿洖绌轰粨")
                    return self._empty_report()
            except Exception as e:
                logger.warning(f"妯"瀷璋冪敤寮傚父锛堢{attempt+1}娆★級锛歿e}")
                if attempt == max_retries - 1:
                    return self._empty_report()
        
        return self._empty_report()

    def _empty_report(self) -> TraderReport:
        """杩斿洖绌轰粨鎶ュ憡"""
        return TraderReport(
            date=datetime.now().strftime("%Y-%m-%d"),
            decision="HOLD",
            stocks=[],
            market_view="妯"瀷璋冪敤寮傚父锛屾殏鏃犲喅绛?,
            risk_level="鏈煡",
            total_position=0,
            raw_reasoning="",
        )

    def to_json(self, report: TraderReport) -> str:
        """搴忓垪鍖栨姤鍛婁负JSON"""
        data = {
            "鏃ユ湡": report.date,
            "鍐崇瓥": report.decision,
            "澶х洏瑙傜偣": report.market_view,
            "椋庨櫓绛夌骇": report.risk_level,
            "鎬讳粨浣?: f"{report.total_position}%",
            "鎺ㄨ崘鑲＄エ": [
                {
                    "浠ｇ爜": s.code,
                    "鍚嶇О": s.name,
                    "鎿嶄綔": s.action,
                    "涔板叆鍖洪棿": f"{s.entry_price_min:.2f}锝瀧s.entry_price_max:.2f}" if s.action == "BUY" else "-",
                    "姝㈡崯浠?: f"{s.stop_loss:.2f}" if s.action == "BUY" else "-",
                    "姝㈢泩浠?": f"{s.take_profit_1:.2f}" if s.action == "BUY" else "-",
                    "姝㈢泩浠?": f"{s.take_profit_2:.2f}" if s.action == "BUY" else "-",
                    "浠撲綅": f"{s.position_pct}%" if s.action == "BUY" else "-",
                    "鐞嗙敱": s.reason,
                }
                for s in report.stocks
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def format_report_for_feishu(self, report: TraderReport) -> str:
        """鏍煎紡鍖栭涔︽帹閫佹枃鏈?""
        lines = [
            f"馃搳 **姣忔棩浜ゆ槗鍐崇瓥鎶ュ憡** | {report.date}",
            f"",
            f"**澶х洏瑙傜偣**锛歿report.market_view}",
            f"**椋庨櫓绛夌骇**锛歿report.risk_level}",
            f"**鎬讳粨浣?*锛歿report.total_position}%",
            f"",
            f"**{'-'*30}**",
        ]
        
        for i, s in enumerate(report.stocks, 1):
            if s.action == "BUY":
                lines.extend([
                    f"",
                    f"馃搶 **{i}. {s.name}锛坽s.code}锛?*",
                    f"   鎿嶄綔锛氣渽 **涔板叆**",
                    f"   涔板叆鍖洪棿锛歿s.entry_price_min:.2f}锝瀧s.entry_price_max:.2f}",
                    f"   姝㈡崯浠凤細馃敶 {s.stop_loss:.2f}锛?{(1-s.stop_loss/s.entry_price_max)*100:.1f}%锛?,
                    f"   绗竴姝㈢泩锛氿煙?{s.take_profit_1:.2f}锛?{(s.take_profit_1/s.entry_price_max-1)*100:.1f}%锛?,
                    f"   绗簩姝㈢泩锛氿煙?{s.take_profit_2:.2f}锛?{(s.take_profit_2/s.entry_price_max-1)*100:.1f}%锛?,
                    f"   浠撲綅锛歿s.position_pct}%锛堢害{self.account_size*s.position_pct//10000/100:.0f}涓囧厓锛?,
                    f"   鐞嗙敱锛歿s.reason}",
                ])
            elif s.action == "HOLD":
                lines.extend([
                    f"",
                    f"鈴革笍 **{i}. 绌轰粨瑙傛湜**",
                    f"   鍘熷洜锛歿s.reason}",
                ])
        
        lines.extend([
            f"",
            f"**{'-'*30}**",
            f"鈿狅笍 浠ヤ笂浠呬緵鍙傝€冿紝鑲"競鏈夐闄╋紝鎶曡祫闇€璋ㄦ厧",
            f"",
            f"鈥斺€?Model 4 | Jack Chen锛?0骞村崕灏旇浜ゆ槗鍛橈級",
        ])
        
        return "\n".join(lines)


# ========== 蹇嵎璋冪敤鍏ュ彛 ==========

def run_trader_decision(screener_stocks: List[Dict], market_analysis: str = "") -> TraderReport:
    """蹇嵎璋冪敤鍑芥暟"""
    agent = TraderAgent()
    return agent.make_decision(screener_stocks, market_analysis)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    # 娴嬭瘯
    test_stocks = [
        {"code": "600519", "name": "璐靛窞鑼呭彴", "market_cap": 2200},
        {"code": "000858", "name": "浜旂伯娑?, "market_cap": 1800},
        {"code": "300750", "name": "瀹佸痉鏃朵唬", "market_cap": 900},
    ]
    
    report = run_trader_decision(test_stocks, "涓婅瘉鎸囨暟绔欑ǔ3300锛屾垚浜ら噺娓╁拰鏀惧ぇ锛岀煭绾垮亸澶?)
    print(f"\n鍐崇瓥缁撴灉锛歿report.decision}")
    print(f"鎬讳粨浣嶏細{report.total_position}%")
    print(agent.to_json(report))
