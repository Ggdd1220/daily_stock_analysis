# -*- coding: utf-8 -*-
"""
===================================
宏观策略模块 - 资金流 + 舆情监控
===================================

第三章：前瞻信号与"聪明钱"动向

数据来源：
- akshare（资金流数据）
- yfinance（美债收益率）

使用方式：
    from macro_strategy import MacroStrategyMonitor
    monitor = MacroStrategyMonitor()
    report = monitor.generate_macro_report()
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class NorthMoneyFlow:
    """北向资金"""
    date: str = ""
    north_net_inflow: float = 0.0
    north_sh_net_inflow: float = 0.0
    north_sz_net_inflow: float = 0.0
    history_5d: List[float] = field(default_factory=list)


@dataclass
class MarginData:
    """融资融券数据"""
    date: str = ""
    margin_balance: float = 0.0
    margin_balance_change: float = 0.0
    short_balance: float = 0.0


@dataclass
class ETFFundFlow:
    """ETF申赎数据"""
    date: str = ""
    etf_total_net_inflow: float = 0.0
    etf_inflow_gold: float = 0.0
    etf_inflow_money: float = 0.0


@dataclass
class MainFundFlow:
    """主力资金流"""
    date: str = ""
    main_net_inflow: float = 0.0
    super_net_inflow: float = 0.0
    large_net_inflow: float = 0.0


@dataclass
class USYieldData:
    """美债收益率"""
    date: str = ""
    yield_10y: float = 0.0
    yield_2y: float = 0.0
    yield_spread: float = 0.0
    change_bps_1d: float = 0.0
    signal: str = "观望"


@dataclass
class MacroReport:
    """宏观策略报告"""
    north_money: Optional[NorthMoneyFlow] = None
    margin: Optional[MarginData] = None
    etf_flow: Optional[ETFFundFlow] = None
    main_flow: Optional[MainFundFlow] = None
    us_yield: Optional[USYieldData] = None
    composite_score: float = 50.0
    risk_level: str = "中等"
    strategy_tip: str = ""


class MacroStrategyMonitor:
    """宏观策略监控器：资金流 + 美债 + 舆情信号"""

    def __init__(self):
        self._akshare_available = self._check_akshare()
        self._yfinance_available = self._check_yfinance()
        logger.info(f"宏观策略监控器: akshare={self._akshare_available}, yfinance={self._yfinance_available}")

    def _check_akshare(self) -> bool:
        try:
            import akshare as ak
            return True
        except ImportError:
            logger.warning("akshare 未安装")
            return False

    def _check_yfinance(self) -> bool:
        try:
            import yfinance as yf
            return True
        except ImportError:
            logger.warning("yfinance 未安装")
            return False

    def _safe_get_field(self, row, field_names: List[str]):
        """安全获取字段，兼容多种命名"""
        for name in field_names:
            try:
                val = row.get(name)
                if val is not None and str(val).strip() not in ['', 'nan', 'None', '-']:
                    return val
            except:
                pass
        return None

    # ---- 1. 北向资金 ----
    def get_north_money_flow(self) -> Optional[NorthMoneyFlow]:
        if not self._akshare_available:
            return None
        try:
            import akshare as ak
            data = ak.stock_hsgt_fund_flow_summary_em()
            # 筛选北向数据（资金方向='北向'）
            north_df = data[data['资金方向'] == '北向'] if '资金方向' in data.columns else data
            # 按板块拆分
            sh_df = north_df[north_df['板块'].str.contains('沪股通', na=False)] if '板块' in north_df.columns else north_df
            sz_df = north_df[north_df['板块'].str.contains('深股通', na=False)] if '板块' in north_df.columns else north_df
            # 成交净买额（单位：亿元）
            sh_net = float(sh_df['成交净买额'].sum()) if len(sh_df) > 0 else 0.0
            sz_net = float(sz_df['成交净买额'].sum()) if len(sz_df) > 0 else 0.0
            net_inflow_today = sh_net + sz_net
            history_5d = []
            for i in range(min(5, len(data))):
                row = data.iloc[i]
                net_val = row.get('成交净买额') or row.get('当日成交净买额')
                if net_val is not None:
                    try:
                        history_5d.append(float(net_val))
                    except:
                        pass
            result = NorthMoneyFlow(
                date=str(date.today()),
                north_net_inflow=net_inflow_today,
                north_sh_net_inflow=sh_net,
                north_sz_net_inflow=sz_net,
                history_5d=history_5d
            )
            logger.info(f"北向资金: {result.north_net_inflow:+.2f}亿元 (沪股通:{sh_net:+.2f} 深股通:{sz_net:+.2f})")
            return result
        except Exception as e:
            logger.warning(f"获取北向资金失败: {e}")
            return None

    # ---- 2. 融资融券 ----
    def get_margin_data(self) -> Optional[MarginData]:
        if not self._akshare_available:
            return None
        try:
            import akshare as ak
            # 汇总所有标的的融资余额（单位：万元 → 亿元）
            data = ak.stock_margin_detail_sse()
            if data is None or data.empty:
                return None
            # 融资余额（合计）
            margin_balance = float(data['融资余额'].sum()) / 10000
            # 融资余额变化 = 今日买入 - 今日偿还（估算）
            margin_buy = float(data['融资买入额'].sum()) / 10000
            margin_repay = float(data['融资偿还额'].sum()) / 10000
            margin_change = margin_buy - margin_repay
            # 融券余额（合计）
            short_balance = float(data['融券余量金额'].sum()) / 10000 if '融券余量金额' in data.columns else 0.0
            result = MarginData(
                date=str(date.today()),
                margin_balance=margin_balance,
                margin_balance_change=margin_change,
                short_balance=short_balance
            )
            logger.info(f"融资余额: {result.margin_balance:.2f}亿元, 变化: {result.margin_balance_change:+.2f}亿元")
            return result
        except Exception as e:
            logger.warning(f"获取融资融券数据失败: {e}")
            return None

    # ---- 3. ETF申赎 ----
    def get_etf_fund_flow(self) -> Optional[ETFFundFlow]:
        # akshare 当前无直接 ETF 申赎数据接口，etf_fund_flow 已移除
        # 返回 None 不阻塞其他数据
        logger.info("ETF申赎: 暂无可靠数据源（N/A）")
        return None

    # ---- 4. 主力资金 ----
    def get_main_fund_flow(self) -> Optional[MainFundFlow]:
        if not self._akshare_available:
            return None
        try:
            import akshare as ak
            # stock_main_fund_flow 会卡住，改用 stock_market_fund_flow
            data = ak.stock_market_fund_flow()
            if data is None or data.empty:
                return None
            today = data.iloc[0]
            # API 返回值单位是元，除以 10000 转万元，再除 10000 转亿元（÷1亿）
            main_net = float(today.get('主力净流入-净额', 0)) / 100000000
            super_net = float(today.get('超大单净流入-净额', 0)) / 100000000
            large_net = float(today.get('大单净流入-净额', 0)) / 100000000
            result = MainFundFlow(
                date=str(date.today()),
                main_net_inflow=main_net,
                super_net_inflow=super_net,
                large_net_inflow=large_net
            )
            logger.info(f"主力资金: {result.main_net_inflow:+.2f}亿元 (超大单:{super_net:+.2f} 大单:{large_net:+.2f})")
            return result
        except Exception as e:
            logger.warning(f"获取主力资金流失败: {e}")
            return None

        # ---- 5. 美债收益率 ----
    def get_us_treasury_yield(self) -> Optional[USYieldData]:
        try:
            import requests
            today_str = date.today().strftime('%Y-%m-%d')
            # FRED 公开数据，无需 API Key
            # 10年期国债收益率
            url10 = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&vintage_date={today_str}'
            r10 = requests.get(url10, timeout=8)
            lines10 = r10.text.strip().split('\n')
            last10 = lines10[-1].split(',')
            yield_10y = float(last10[1])
            # 2年期国债收益率
            url2 = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2&vintage_date={today_str}'
            r2 = requests.get(url2, timeout=8)
            lines2 = r2.text.strip().split('\n')
            last2 = lines2[-1].split(',')
            yield_2y = float(last2[1])
            yield_spread = yield_10y - yield_2y
            # 1日变化（bp）
            prev10 = float(lines10[-2].split(',')[1]) if len(lines10) >= 2 else yield_10y
            change_1d = (yield_10y - prev10) * 100
            if yield_10y > 4.4:
                signal = "风险偏好高 → 利好科技/成长股"
            elif yield_10y < 4.3:
                signal = "避险/衰退预期 → 资金流向防御品种"
            else:
                signal = "中性观望"
            result = USYieldData(
                date=str(date.today()),
                yield_10y=yield_10y,
                yield_2y=yield_2y,
                yield_spread=yield_spread,
                change_bps_1d=change_1d,
                signal=signal
            )
            logger.info(f"美债10Y: {result.yield_10y:.3f}% 2Y:{result.yield_2y:.3f}% 利差:{result.yield_spread:+.3f}% | {result.signal}")
            return result
        except Exception as e:
            logger.warning(f"获取美债数据失败: {e}")
            return None

    # ---- 综合报告 ----
    def generate_macro_report(self) -> MacroReport:
        logger.info("=== 生成宏观策略报告 ===")
        report = MacroReport()
        try:
            report.north_money = self.get_north_money_flow()
        except Exception as e:
            logger.warning(f"北向资金: {e}")
        try:
            report.margin = self.get_margin_data()
        except Exception as e:
            logger.warning(f"融资融券: {e}")
        try:
            report.etf_flow = self.get_etf_fund_flow()
        except Exception as e:
            logger.warning(f"ETF申赎: {e}")
        try:
            report.main_flow = self.get_main_fund_flow()
        except Exception as e:
            logger.warning(f"主力资金: {e}")
        try:
            report.us_yield = self.get_us_treasury_yield()
        except Exception as e:
            logger.warning(f"美债: {e}")
        report.composite_score = self._calculate_composite_score(report)
        report.risk_level = self._calculate_risk_level(report)
        report.strategy_tip = self._generate_strategy_tip(report)
        logger.info(f"宏观报告: 综合={report.composite_score:.0f}, 风险={report.risk_level}")
        return report

    def _sg(self, obj, attr, default="N/A"):
        """Safe getattr - returns default if attribute is None or missing"""
        if obj is None:
            return default
        val = getattr(obj, attr, None)
        if val is None:
            return default
        return val
    

    def format_markdown_report(self, report) -> str:
        """格式化宏观策略报告为Markdown"""
        try:
            lines = [
                "\n## 第三章 宏观策略与市场情绪",
                "",
                "### 一、宏观信号",
                "",
                "**美债10年期收益率**: " + str(self._sg(report, 'yield_10y', '获取失败')) + " | " + str(self._sg(report, 'signal', '获取失败')),
                "",
                "**北向资金**: 今日" + str(self._sg(report, 'north_money_today', '获取失败')) + " | 近5日" + str(self._sg(report, 'north_money_5d', '获取失败')),
                "",
                "**融资融券余额**: " + str(self._sg(report, 'margin_balance', '获取失败')),
                "",
                "**ETF申赎净额**: " + str(self._sg(report, 'etf_net', '获取失败')),
                "",
                "**主力资金流**: " + str(self._sg(report, 'main_money_flow', '获取失败')),
                "",
            ]
            
            # 综合评分
            score = self._sg(report, 'comprehensive_score', None)
            if score is None or score == "N/A":
                score_str = "获取失败"
            else:
                try:
                    score_str = f"**{score.score}/100**" if hasattr(score, 'score') else str(score)
                except:
                    score_str = str(score)
            
            risk = self._sg(report, 'risk_level', '获取失败')
            action = self._sg(report, 'action', '获取失败')
            
            lines.extend([
                "**综合评分**: " + score_str + " | 风险等级: **" + str(risk) + "** | 操作建议: **" + str(action) + "**",
                "",
                "### 二、市场情绪",
                "",
                str(self._sg(report, 'market_review_section', '获取失败')),
                "",
                "### 三、热点板块",
                "",
                str(self._sg(report, 'hot_sector_section', '获取失败')),
            ])
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.warning(f"Format macro report error: {e}")
            return "[第三章宏观策略报告生成失败]"

    def _calculate_composite_score(self, report: MacroReport) -> float:
        score = 50.0
        if report.north_money:
            n = report.north_money
            if n.north_net_inflow > 50: score += 20
            elif n.north_net_inflow > 20: score += 15
            elif n.north_net_inflow > 0: score += 10
            elif n.north_net_inflow > -20: score -= 5
            else: score -= 15
        if report.us_yield:
            u = report.us_yield
            if u.yield_10y > 4.4: score += 10
            elif u.yield_10y < 4.3: score -= 5
            if u.change_bps_1d > 10: score -= 5
        if report.margin:
            m = report.margin
            if m.margin_balance_change > 50: score += 10
            elif m.margin_balance_change > 20: score += 5
            elif m.margin_balance_change < -50: score -= 10
        if report.etf_flow:
            e = report.etf_flow
            if e.etf_total_net_inflow > 50: score += 10
            elif e.etf_total_net_inflow < -50: score -= 10
        if report.main_flow:
            mf = report.main_flow
            if mf.main_net_inflow > 100: score += 15
            elif mf.main_net_inflow > 50: score += 10
            elif mf.main_net_inflow < -100: score -= 15
        return max(0, min(100, score))

    def _calculate_risk_level(self, report: MacroReport) -> str:
        score = report.composite_score
        if score >= 70: return "🟢 低风险 - 积极布局"
        elif score >= 55: return "🟡 中低风险 - 稳健做多"
        elif score >= 40: return "🟠 中等风险 - 谨慎操作"
        elif score >= 25: return "🔴 中高风险 - 减仓防御"
        else: return "🚨 高风险 - 清仓回避"

    def _generate_strategy_tip(self, report: MacroReport) -> str:
        tips = []
        risk_signals = []
        if report.north_money and report.north_money.north_net_inflow < -30:
            risk_signals.append("⚠️ 北向资金大幅流出（>30亿），警惕外资撤退")
        if report.us_yield:
            if report.us_yield.change_bps_1d > 10:
                risk_signals.append(f"⚠️ 美债10Y单日飙升 {report.us_yield.change_bps_1d:.0f}bp，通胀预期升温")
            if report.us_yield.yield_10y > 4.6:
                risk_signals.append("🚨 美债10Y > 4.6%，全球流动性收紧信号")
        if report.margin and report.margin.margin_balance_change < -50:
            risk_signals.append("⚠️ 融资余额骤降（>50亿），杠杆资金减仓")
        if report.main_flow and report.main_flow.main_net_inflow < -100:
            risk_signals.append("🚨 主力资金大幅出逃（>100亿），机构撤退")
        if risk_signals:
            tips.append(" | ".join(risk_signals))
            tips.append("建议：降低仓位，增加防御性配置（黄金/货币基金/公用事业）")
        else:
            if report.composite_score >= 60:
                tips.append("✅ 多信号共振偏多，可适度加仓进攻性品种")
            elif report.composite_score >= 45:
                tips.append("⚖️ 信号中性，维持现有仓位，高抛低吸")
            else:
                tips.append("📉 信号偏弱，等待企稳信号，控制仓位")
        return "\n".join(tips) if tips else "⚖️ 暂无明确信号，维持观望"


def get_macro_report() -> str:
    """获取宏观策略报告（快捷函数）"""
    try:
        monitor = MacroStrategyMonitor()
        report = monitor.generate_macro_report()
        return monitor.format_markdown_report(report)
    except Exception as e:
        logger.error(f"生成宏观报告失败: {e}")
        return f"\n\n## 🧭 第三章：前瞻信号与\"聪明钱\"动向\n\n*⚠️ 数据获取失败: {e}*\n\n"


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', stream=sys.stdout)
    report = get_macro_report()
    print(report)
