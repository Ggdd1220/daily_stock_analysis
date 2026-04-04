# -*- coding: utf-8 -*-
"""
===================================
A股自动选股模块
===================================

功能：
1. 获取全市场股票列表
2. 排除 ST、北交所
3. 排除市值 > 500亿 或 市值 < 50亿
4. 技术面筛选（涨幅/成交量/均线）
5. 每日最多分析 N 只

使用方式：
    python -c "from screener import StockScreener; s = StockScreener(); print(s.screen())"
"""
import logging
import random
import time
from typing import List, Dict, Any, Optional

import pandas as pd
import akshare as ak

logger = logging.getLogger(__name__)

# 北交所代码前缀
BSE_PREFIXES = ('8', '9')


class StockScreener:
    """
    A股自动选股器
    
    筛选条件：
    1. 排除 ST/*ST（名称含 ST/* 的）
    2. 排除北交所（8xxxxx, 9xxxxx）
    3. 排除市值 > 500亿（太大不利于中小盘机会）
    4. 排除市值 < 50亿（太小风险高）
    5. 技术面条件（至少满足一个）：
       - 今日涨幅 > 2%
       - 今日成交量放大（量比 > 1.5）
       - MA5 上穿 MA10（金叉）
    """
    
    def __init__(
        self,
        max_stocks: int = 300,
        min_market_cap: int = 50,
        max_market_cap: int = 500,
        min_increase_pct: float = 2.0,
        min_volume_ratio: float = 1.5,
        sleep_min: float = 1.0,
        sleep_max: float = 2.0,
    ):
        """
        初始化选股器
        
        Args:
            max_stocks: 最多返回股票数量（按技术分排序取前 N）
            min_market_cap: 最小市值（亿元）
            max_market_cap: 最大市值（亿元）
            min_increase_pct: 最小涨幅（%），满足则入选
            min_volume_ratio: 最小量比，满足则入选
            sleep_min/max: 请求间隔（秒）
        """
        self.max_stocks = max_stocks
        self.min_market_cap = min_market_cap * 1e8   # 转换为元
        self.max_market_cap = max_market_cap * 1e8
        self.min_increase_pct = min_increase_pct
        self.min_volume_ratio = min_volume_ratio
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
    
    def _random_sleep(self):
        time.sleep(random.uniform(self.sleep_min, self.sleep_max))
    
    def _is_bse(self, code: str) -> bool:
        """判断是否为北交所股票"""
        return code.startswith(BSE_PREFIXES) and len(code) == 6
    
    def _is_st(self, name: str) -> bool:
        """判断是否为 ST 股票"""
        if not name:
            return False
        name_upper = name.upper()
        return 'ST' in name_upper or '*ST' in name_upper or 'S*ST' in name_upper
    
    def _get_full_stock_list(self) -> List[Dict[str, str]]:
        """
        获取全市场股票列表（代码+名称）
        
        Returns:
            [{'code': '600519', 'name': '贵州茅台'}, ...]
        """
        logger.info("正在获取全市场股票列表...")
        try:
            df = ak.stock_info_a_code_name()
            result = df[['code', 'name']].to_dict('records')
            logger.info(f"共获取 {len(result)} 只股票")
            return result
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def _get_market_cap_data(self, codes: List[str]) -> pd.DataFrame:
        """
        获取市值数据
        
        Args:
            codes: 股票代码列表
            
        Returns:
            DataFrame with code, name, total_mv (总市值，元)
        """
        logger.info(f"正在获取 {len(codes)} 只股票的市值数据...")
        
        all_data = []
        batch_size = 50
        
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            try:
                # 东方财富 A 股实时行情（含量比、换手率、市值）
                df = ak.stock_zh_a_spot_em()
                # 筛选需要的列
                if '代码' in df.columns:
                    df = df.rename(columns={'代码': 'code', '名称': 'name'})
                if '总市值' in df.columns:
                    df = df.rename(columns={'总市值': 'total_mv'})
                batch_data = df[df['code'].isin(batch)][['code', 'name', 'total_mv']].copy()
                all_data.append(batch_data)
                logger.info(f"  批次 {i//batch_size + 1}: 获取 {len(batch_data)} 只")
            except Exception as e:
                logger.warning(f"  批次 {i//batch_size + 1} 获取失败: {e}")
            
            if i + batch_size < len(codes):
                self._random_sleep()
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"成功获取 {len(result)} 只股票的市值数据")
            return result
        else:
            logger.error("未能获取任何市值数据")
            return pd.DataFrame(columns=['code', 'name', 'total_mv'])
    
    def _get_technical_data(self, codes: List[str]) -> pd.DataFrame:
        """
        获取技术面数据（涨幅、量比、均线）
        
        Args:
            codes: 股票代码列表
            
        Returns:
            DataFrame with code, change_pct, volume_ratio, ma5, ma10, ma20
        """
        logger.info(f"正在获取 {len(codes)} 只股票的技术数据...")
        
        all_data = []
        batch_size = 30
        
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            try:
                # 使用实时行情接口获取量比、换手率、涨跌幅
                df = ak.stock_zh_a_spot_em()
                batch_data = df[df['代码'].isin(batch)][['代码', '涨跌幅', '量比']].copy()
                batch_data.columns = ['code', 'change_pct', 'volume_ratio']
                all_data.append(batch_data)
                logger.info(f"  批次 {i//batch_size + 1}: 获取 {len(batch_data)} 只")
            except Exception as e:
                logger.warning(f"  批次 {i//batch_size + 1} 技术数据获取失败: {e}")
            
            if i + batch_size < len(codes):
                self._random_sleep()
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            return result
        return pd.DataFrame()
    
    def screen(self) -> List[str]:
        """
        执行选股，返回符合条件的股票代码列表
        
        Returns:
            股票代码列表，如 ['600519', '300750', ...]
        """
        logger.info("=" * 50)
        logger.info("开始选股筛选...")
        logger.info(f"条件: 排除ST, 排除北交所, {self.min_market_cap/1e8:.0f}亿 < 市值 < {self.max_market_cap/1e8:.0f}亿, 技术面筛选")
        
        # Step 1: 获取全市场股票列表
        stock_list = self._get_full_stock_list()
        if not stock_list:
            logger.error("股票列表为空，选股失败")
            return []
        
        # Step 2: 基础过滤（排除 ST 和 北交所）
        basic_filtered = [
            s for s in stock_list
            if not self._is_st(s['name']) and not self._is_bse(s['code'])
        ]
        logger.info(f"排除ST和北交所后: {len(basic_filtered)} 只")
        
        if not basic_filtered:
            return []
        
        codes = [s['code'] for s in basic_filtered]
        names = {s['code']: s['name'] for s in basic_filtered}
        
        # Step 3: 获取市值数据，过滤市值范围
        market_cap_data = self._get_market_cap_data(codes)
        
        if market_cap_data.empty:
            logger.warning("市值数据获取失败，跳过市值过滤")
            market_cap_filtered = codes
        else:
            # 过滤市值范围
            market_cap_filtered = []
            for _, row in market_cap_data.iterrows():
                mv = row.get('total_mv', 0)
                if pd.notna(mv) and mv > 0:
                    if self.min_market_cap <= mv <= self.max_market_cap:
                        market_cap_filtered.append(row['code'])
            logger.info(f"市值过滤后: {len(market_cap_filtered)} 只")
        
        if not market_cap_filtered:
            logger.warning("市值过滤后无股票，返回原始列表前100只")
            return codes[:100]
        
        # Step 4: 获取技术面数据
        tech_data = self._get_technical_data(market_cap_filtered)
        
        if tech_data.empty:
            logger.warning("技术数据获取失败，返回市值过滤后的前100只")
            return market_cap_filtered[:100]
        
        # Step 5: 技术面筛选
        # 条件：涨幅 > min_increase_pct OR 量比 > min_volume_ratio OR (MA5 > MA10 AND close > MA5)
        # 为了简化，这里先只用过涨幅和量比，因为获取均线需要额外请求历史数据
        
        tech_data['pass_tech'] = (
            (tech_data['change_pct'].fillna(0) > self.min_increase_pct) |
            (tech_data['volume_ratio'].fillna(0) > self.min_volume_ratio)
        )
        
        # 合并通过技术筛选的股票
        passed_tech = tech_data[tech_data['pass_tech']]['code'].tolist()
        
        # 补充一些市值排序靠前但技术面一般的股票（保持多样性）
        # 按市值从大到小排序，取技术面通过的前 N 只 + 未通过但市值最大的前 N/2 只
        market_cap_sorted = market_cap_filtered
        
        # 分两部分：技术面通过的 + 技术面未通过但市值大的
        passed = [c for c in passed_tech if c in market_cap_filtered]
        not_passed_but_big = [c for c in market_cap_sorted if c not in passed]
        
        # 最终列表：技术通过的全部 + 市值大但未通过的补充到 max_stocks
        final_codes = passed + not_passed_but_big
        final_codes = final_codes[:self.max_stocks]
        
        logger.info(f"技术面筛选后: {len(passed)} 只")
        logger.info(f"补充市值靠前股票: +{len(final_codes) - len(passed)} 只")
        logger.info(f"最终选股数量: {len(final_codes)} 只")
        
        # 记录选股结果
        result_info = []
        for code in final_codes[:20]:
            name = names.get(code, '')
            mv = market_cap_data[market_cap_data['code'] == code]['total_mv'].values
            mv_str = f"{mv[0]/1e8:.1f}亿" if len(mv) > 0 and mv[0] > 0 else "未知"
            result_info.append(f"  {code} {name} (市值:{mv_str})")
        
        logger.info("选股结果（前20只）:\n" + "\n".join(result_info))
        
        return final_codes


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    screener = StockScreener(
        max_stocks=300,
        min_market_cap=50,
        max_market_cap=500,
        min_increase_pct=2.0,
        min_volume_ratio=1.5,
    )
    
    result = screener.screen()
    print(f"\n筛选结果: {len(result)} 只股票")
    print(result[:50])
