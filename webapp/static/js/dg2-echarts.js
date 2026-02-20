/* ═══════════════════════════════════════════════════════════════════════
   DG2 ECharts Theme — Palantir Blueprint Dark
   Shared across all chart pages. Load after echarts.min.js.
   ═══════════════════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  var DG2_THEME = {
    backgroundColor: 'transparent',
    color: [
      '#2D72D2','#29A634','#D1980B','#D33D17','#9D3F9D',
      '#00A396','#DB2C6F','#7961DB','#8EB125','#147EB3',
      '#43BF4D','#FFC940','#634DBF','#FF6E4A','#2EE6D6',
    ],
    textStyle: {
      color: '#ABB3BF',
      fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
      fontSize: 11,
    },
    title: {
      textStyle: { color: '#C5CBD3', fontSize: 13, fontWeight: 600 },
      subtextStyle: { color: '#5F6B7C', fontSize: 11 },
    },
    legend: {
      textStyle: { color: '#ABB3BF', fontSize: 10 },
      pageTextStyle: { color: '#ABB3BF' },
      pageIconColor: '#5F6B7C',
      pageIconInactiveColor: '#383E47',
    },
    tooltip: {
      backgroundColor: '#1C2127',
      borderColor: '#2F343C',
      borderWidth: 1,
      textStyle: { color: '#C5CBD3', fontSize: 12 },
      extraCssText: 'box-shadow:0 2px 8px rgba(0,0,0,0.5);border-radius:4px;',
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: '#2F343C' } },
      axisTick: { lineStyle: { color: '#383E47' } },
      axisLabel: { color: '#8F99A8', fontSize: 10 },
      splitLine: { lineStyle: { color: '#252A31' } },
    },
    valueAxis: {
      axisLine: { lineStyle: { color: '#2F343C' } },
      axisTick: { lineStyle: { color: '#383E47' } },
      axisLabel: { color: '#8F99A8', fontSize: 10 },
      splitLine: { lineStyle: { color: '#252A31' } },
      nameTextStyle: { color: '#5F6B7C', fontSize: 10 },
    },
    line: {
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2 },
      smooth: false,
    },
    bar: {
      barMaxWidth: 40,
    },
  };

  echarts.registerTheme('dg2', DG2_THEME);

  /* ── initChart(domId) ──
     Creates an ECharts instance with the DG2 theme and auto-resize. */
  window.initChart = function(domId) {
    var el = document.getElementById(domId);
    if (!el) return null;
    /* Dispose any existing instance on this element */
    var existing = echarts.getInstanceByDom(el);
    if (existing) existing.dispose();
    var chart = echarts.init(el, 'dg2');
    new ResizeObserver(function() { chart.resize(); }).observe(el);
    return chart;
  };

  /* ── Format helpers ── */
  window.ecFmtNum = function(n) {
    if (n == null) return '\u2014';
    if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
    if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toLocaleString();
  };

  window.ecFmtDollars = function(n) {
    if (n == null) return '\u2014';
    return '$' + window.ecFmtNum(n);
  };

  window.ecFmtPercent = function(n) {
    if (n == null) return '\u2014';
    return Number(n).toFixed(2) + '%';
  };

  window.ecFmtLifeExp = function(n) {
    if (n == null) return '\u2014';
    return Number(n).toFixed(1) + ' yrs';
  };

})();
