import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, Terminal, Database, Download, CheckCircle2, 
  AlertCircle, Loader2, TrendingUp, Layers, Settings, 
  RefreshCw, FileSpreadsheet, Cpu, ArrowUpRight, Activity, 
  Sparkles, Clock, ChevronRight, Check, ArrowDownRight, Info
} from 'lucide-react';

// ==========================================
// 1. 领域模拟数据定义 (Semiconductor/OLED Yield)
// ==========================================
const INITIAL_PIPELINES = [
  {
    id: 'eda_pipeline',
    name: 'EDA 自动化流水线',
    type: 'Raw Excel Pull',
    target: 'V3_Yield_Summary.xlsx',
    successRate: 99.4,
    rowsExtracted: '12,480',
    sessionId: 'EDA_SSID_88F092',
    lastSync: '刚刚',
    status: 'idle' // 'idle' | 'running' | 'success'
  },
  {
    id: 'finereport_api',
    name: '帆软报表 (FineReport) 接口',
    type: 'REST API & Scraping',
    target: 'CT_Abnormal_Management',
    successRate: 98.7,
    rowsExtracted: '3,429',
    sessionId: 'FR_SID_48D2A1',
    lastSync: '刚刚',
    status: 'idle'
  }
];

const YIELD_SUMMARY_MOCK = [
  { segment: 'ARRAY (阵列厂)', actual: '94.25%', bpTarget: '94.70%', pullUpTarget: '95.00%', gap: '-0.45%', status: 'fail', reason: 'Module 3 线路蚀刻不均，造成局部断路风险，LLM 已关联 CT 异常第 #1 项。' },
  { segment: 'OLED (蒸镀/封装)', actual: '82.12%', bpTarget: '82.00%', pullUpTarget: '82.50%', gap: '+0.12%', status: 'pass', reason: '蒸镀有机材料纯度提升，发光效率稳定，当前良率微幅超越 BP 目标。' },
  { segment: 'TP (触控面板)', actual: '98.15%', bpTarget: '98.20%', pullUpTarget: '98.50%', gap: '-0.05%', status: 'warning', reason: '贴合气泡异常率波动，已通过控制系统调整排气阀压力，预计下班次恢复。' },
  { segment: 'CELL TEST (CT模组)', actual: '91.80%', bpTarget: '92.30%', pullUpTarget: '92.80%', gap: '-0.50%', status: 'fail', reason: '主要受 ARRAY 侧传导划伤残余影响，CT 测试端电学表现出现集中性低良。' }
];

const EXCEPTIONS_MOCK = [
  { id: 'ERR-01', site: 'CELL TEST', item: '电阻测试值异常偏高', severity: 'High', count: '45 批次', analysis: '12.5" 屏体触控引脚过孔不通，排查原因为前道过孔偏位，已挂起风险控制。' },
  { id: 'ERR-02', site: 'ARRAY', item: '表面颗粒物电性短路', severity: 'Medium', count: '18 批次', analysis: '曝光机台腔体内壁附着物脱落，已通知设备工程对 L20 机台进行 PM 维护。' },
  { id: 'ERR-03', site: 'OLED', item: '封装膜层（TFE）边缘发黑', severity: 'High', count: '32 批次', analysis: '边缘喷墨干燥温度超标，造成膜层封装失效导致水汽入侵，工艺窗口已收紧 2℃。' }
];

const RISKS_MOCK = [
  { item: '55" OLED TV Panel 阵列大面积断路风险', forecast: '本月良率预估拉低 0.25%', status: '管控中', plan: '预计 05/28 释放首批改善流片' },
  { item: '6.7" 柔性手机屏折叠区闪屏风险', forecast: '影响排产良率 ~1.2%', status: '评估中', plan: '明日召开专项品质判定会确定工艺释放标准' }
];

const STAGES = {
  IDLE: 'idle',
  LOGGING_IN: 'logging_in',
  SCRAPING_DATA: 'scraping_data',
  PROCESSING: 'processing',
  LLM_ANALYSIS: 'llm_analysis',
  GENERATING_EXCEL: 'generating_excel',
  COMPLETED: 'completed'
};

// ==========================================
// 2. 日志文本模板流 (真实再现后端核心行为)
// ==========================================
const LOG_MESSAGES = {
  [STAGES.LOGGING_IN]: [
    { type: 'info', text: '🌐 正在初始化与内网 EDA 及帆软决策系统的安全网关连接...' },
    { type: 'info', text: '🔑 载入 global.yaml 安全密文，配置加载单例 ConfigLoader 初始化成功。' },
    { type: 'success', text: '🎯 帆软决策服务 Session 握手成功，捕获当前会话 ID: [FR_SID_48D2A1]' },
    { type: 'success', text: '🎯 EDA 核心数据库权限验证通过，授权 Token 注入成功。' }
  ],
  [STAGES.SCRAPING_DATA]: [
    { type: 'info', text: '📥 开始读取 V3良率汇总表、CT异常管理表源路径...' },
    { type: 'info', text: '⚡ 触发 L1 Parquet 文件快照缓存策略：检测到源 Excel 文件修改时间晚于 Parquet。' },
    { type: 'success', text: '📦 Excel 转本地快照完成，写入 data/temp/*.parquet。累计读取 15,909 行原始数据。' },
    { type: 'success', text: '✓ 捕获到锁定文件 (~$V3屏体良率日报.xlsx)，已自动平滑解析至真实物理路径。' }
  ],
  [STAGES.PROCESSING]: [
    { type: 'info', text: '⚙️ 启动 DataProcessor 与 ExceptionProcessor 核心解析引擎...' },
    { type: 'info', text: '🔍 正在使用正则表达式匹配 BP 目标与提拉目标单元格单元 (步长/间距解析模式)...' },
    { type: 'info', text: '📊 自动执行衍生指标计算：Gap = 实际良率 - BP 目标良率。' },
    { type: 'success', text: '✓ ARRAY、OLED、TP、CELL TEST 四大核心厂别良率与目标值解析就绪。' }
  ],
  [STAGES.LLM_ANALYSIS]: [
    { type: 'info', text: '🧠 正在调用 LLMManager 启动生成式 AI 重度分析模块...' },
    { type: 'info', text: '🤖 调用模式: [provider: deepseek-chat] [Model: DeepSeek-V3] [API_Key: ✅]' },
    { type: 'info', text: '💬 正在将良率偏差数据与 CT异常表 进行多表关联，格式化 Prompt 上下文...' },
    { type: 'success', text: '✨ DeepSeek 分析反馈：成功关联 CT异常项 #1 (#ERR-01) 并生成专业级 Gap 原因归因。' },
    { type: 'success', text: '✨ 连续三日与三周趋势研判生成完毕：触控贴合工段存在微幅下行趋势风险。' }
  ],
  [STAGES.GENERATING_EXCEL]: [
    { type: 'info', text: '📝 复制标准 Excel 模板资源：resources/template_v3.xlsx' },
    { type: 'info', text: '📝 正在向模板单元格写入当日 Gap 解释、当日异常及已知异常历史表...' },
    { type: 'info', text: '🎨 启动 FontProcessor 样式流水线。执行底层 zip 解包，提取 sharedStrings.xml...' },
    { type: 'success', text: '🎨 通过 xlsxwriter 创建富文本供体，将 AI 归因结论优雅注入目标单元格 XML，确保 Excel 自动换行美观。' },
    { type: 'success', text: '🎉 最终物理文件生成完毕：output/V3_屏体良率日报_20260526.xlsx' }
  ]
};

export default function YieldAgentDashboard() {
  const [stage, setStage] = useState(STAGES.IDLE);
  const [logs, setLogs] = useState([
    { time: '14:30:00', type: 'system', text: '🤖 智能体前台面板初始化就绪，等待执行指令。' }
  ]);
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'exceptions' | 'risks'
  const [pipelines, setPipelines] = useState(INITIAL_PIPELINES);
  const terminalEndRef = useRef(null);

  // 终端日志自动滚到底部
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // 模拟全自动执行流水线
  const triggerWorkflow = () => {
    if (stage !== STAGES.IDLE && stage !== STAGES.COMPLETED) return;
    
    setStage(STAGES.LOGGING_IN);
    setLogs([{ time: new Date().toLocaleTimeString(), type: 'system', text: '🚀 启动全自动良率日报抓取与生成智能体...' }]);
    
    // 阶段变化调度器
    const runWorkflow = async () => {
      const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
      
      // 更新 Pipeline 运行状态
      setPipelines(prev => prev.map(p => ({ ...p, status: 'running' })));

      // 1. 登录阶段
      await sleep(1500);
      appendLogs(STAGES.LOGGING_IN);
      
      // 2. 抓取数据
      setStage(STAGES.SCRAPING_DATA);
      await sleep(2000);
      appendLogs(STAGES.SCRAPING_DATA);
      setPipelines(prev => prev.map(p => ({ ...p, status: 'success', lastSync: '刚刚' })));

      // 3. 数据处理
      setStage(STAGES.PROCESSING);
      await sleep(1800);
      appendLogs(STAGES.PROCESSING);

      // 4. 大模型分析
      setStage(STAGES.LLM_ANALYSIS);
      await sleep(2500);
      appendLogs(STAGES.LLM_ANALYSIS);

      // 5. Excel 样式重组与导出
      setStage(STAGES.GENERATING_EXCEL);
      await sleep(2000);
      appendLogs(STAGES.GENERATING_EXCEL);

      // 6. 完成
      setStage(STAGES.COMPLETED);
      setLogs(prev => [
        ...prev, 
        { time: new Date().toLocaleTimeString(), type: 'system', text: '🎉 【生成成功】良率日报编译已完美收官！输出物理文件可供下载。' }
      ]);
    };

    runWorkflow();
  };

  const appendLogs = (targetStage) => {
    const messages = LOG_MESSAGES[targetStage];
    if (!messages) return;
    
    const timeStr = new Date().toLocaleTimeString();
    setLogs(prev => [
      ...prev,
      ...messages.map((m, i) => ({
        time: timeStr,
        type: m.type,
        text: m.text
      }))
    ]);
  };

  return (
    <div className="min-h-screen bg-slate-50/60 text-slate-900 font-sans antialiased selection:bg-indigo-50 selection:text-indigo-900">
      
      {/* ==========================================
          页头设计 (Premium Header)
         ========================================== */}
      <header className="border-b border-slate-100 bg-white/80 backdrop-blur-md sticky top-0 z-50 px-8 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-md shadow-indigo-100">
              <Cpu className="h-5 w-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-slate-900">良率日报智能体</h1>
                <span className="text-[10px] bg-indigo-50 text-indigo-600 font-medium px-2 py-0.5 rounded-full border border-indigo-100">
                  Daily Report Agent v2.0
                </span>
              </div>
              <p className="text-xs text-slate-500">
                基于 DDD 架构的数据提取、多维缓存与大模型智能分析系统
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end md:self-auto">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-50 border border-slate-100 px-3 py-1.5 rounded-lg">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Pydantic V2 配置已校验</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-50 border border-slate-100 px-3 py-1.5 rounded-lg">
              <Sparkles className="h-3.5 w-3.5 text-violet-500" />
              <span>模型: DeepSeek-V3</span>
            </div>
          </div>
        </div>
      </header>

      {/* ==========================================
          大画布布局 (Bento Grid Workspace)
         ========================================== */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-12 gap-6">

          {/* 1. 左侧：智能体控制与状态卡片 (Agent Status Panel) - Col span 4 */}
          <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
            
            {/* Bento Card: 智能体状态中控台 */}
            <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm shadow-slate-100/50 flex flex-col gap-5 relative overflow-hidden transition-all duration-300 hover:shadow-md hover:border-slate-200">
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-50/30 rounded-full blur-2xl -z-10" />
              
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold tracking-wider uppercase text-slate-400">状态中控台</span>
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5 ${
                  stage === STAGES.IDLE ? 'bg-slate-100 text-slate-600' :
                  stage === STAGES.COMPLETED ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' :
                  'bg-indigo-50 text-indigo-600 border border-indigo-100 animate-pulse'
                }`}>
                  {stage === STAGES.IDLE && '● 闲置中'}
                  {stage === STAGES.LOGGING_IN && '⚡ 登录验证中'}
                  {stage === STAGES.SCRAPING_DATA && '⚡ 数据拉取中'}
                  {stage === STAGES.PROCESSING && '⚡ 规则解析中'}
                  {stage === STAGES.LLM_ANALYSIS && '✨ LLM 分析中'}
                  {stage === STAGES.GENERATING_EXCEL && '🎨 注入富文本样式'}
                  {stage === STAGES.COMPLETED && '✓ 已就绪'}
                </span>
              </div>

              {/* 核心驱动 Button */}
              <button
                onClick={triggerWorkflow}
                disabled={stage !== STAGES.IDLE && stage !== STAGES.COMPLETED}
                className={`w-full py-3.5 px-4 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition-all duration-300 ${
                  stage !== STAGES.IDLE && stage !== STAGES.COMPLETED
                    ? 'bg-slate-50 text-slate-400 border border-slate-100 cursor-not-allowed'
                    : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-100 hover:shadow-indigo-200 active:scale-[0.98]'
                }`}
              >
                {stage !== STAGES.IDLE && stage !== STAGES.COMPLETED ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>智能体拼命工作中...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 fill-current" />
                    <span>一键全自动良率日报生成</span>
                  </>
                )}
              </button>

              {/* 流程Stepper */}
              <div className="flex flex-col gap-3.5 mt-2 border-t border-slate-100/80 pt-4">
                <div className="text-xs text-slate-400 font-semibold mb-1">执行状态流</div>
                {[
                  { key: STAGES.LOGGING_IN, label: '内网安全通道建立与登录认证' },
                  { key: STAGES.SCRAPING_DATA, label: '多源报表拉取及 Parquet 快照归档' },
                  { key: STAGES.PROCESSING, label: '数据指标提取、清洗与 Gap 自动衍生' },
                  { key: STAGES.LLM_ANALYSIS, label: 'DeepSeek-V3 差异分析与异常归因' },
                  { key: STAGES.GENERATING_EXCEL, label: '写入模板并动态重构 Excel XML 样式' }
                ].map((step, idx) => {
                  const isDone = 
                    stage === STAGES.COMPLETED || 
                    Object.values(STAGES).indexOf(stage) > Object.values(STAGES).indexOf(step.key);
                  const isActive = stage === step.key;

                  return (
                    <div key={step.key} className="flex items-center justify-between text-xs transition-all">
                      <div className="flex items-center gap-2.5">
                        <div className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all duration-300 ${
                          isDone ? 'bg-emerald-50 text-emerald-600 border-emerald-200' :
                          isActive ? 'bg-indigo-50 text-indigo-600 border-indigo-200 shadow-sm' :
                          'bg-slate-50 text-slate-400 border-slate-200/80'
                        }`}>
                          {isDone ? <Check className="h-3 w-3" /> : (idx + 1)}
                        </div>
                        <span className={`font-medium transition-colors ${
                          isDone ? 'text-slate-500 line-through decoration-slate-200' :
                          isActive ? 'text-indigo-600 font-semibold' :
                          'text-slate-400'
                        }`}>
                          {step.label}
                        </span>
                      </div>
                      {isActive && (
                        <div className="flex gap-0.5">
                          <span className="w-1 h-1 bg-indigo-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-1 h-1 bg-indigo-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-1 h-1 bg-indigo-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Bento Card: 数据源监控 */}
            <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm shadow-slate-100/50 flex flex-col gap-4 transition-all duration-300 hover:shadow-md hover:border-slate-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold tracking-wider uppercase text-slate-400">底层数据管道监控</span>
                <Database className="h-4 w-4 text-slate-400" />
              </div>
              
              <div className="flex flex-col gap-4">
                {pipelines.map(pipeline => (
                  <div key={pipeline.id} className="border border-slate-50 rounded-xl p-3.5 bg-slate-50/30 flex flex-col gap-2.5 hover:bg-slate-50/60 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${
                          pipeline.status === 'running' ? 'bg-indigo-500 animate-ping' :
                          pipeline.status === 'success' ? 'bg-emerald-500' : 'bg-slate-300'
                        }`} />
                        <span className="text-xs font-semibold text-slate-700">{pipeline.name}</span>
                      </div>
                      <span className="text-[10px] bg-slate-100 text-slate-500 font-medium px-2 py-0.5 rounded">
                        {pipeline.type}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] border-t border-slate-100/80 pt-2 text-slate-500">
                      <div>
                        <span className="text-slate-400">最新 Session ID:</span>
                        <div className="font-mono text-slate-700 font-medium truncate mt-0.5">{pipeline.sessionId}</div>
                      </div>
                      <div>
                        <span className="text-slate-400">最近提取成功率:</span>
                        <div className="text-slate-700 font-medium mt-0.5 text-emerald-600 font-semibold">{pipeline.successRate}%</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* 2. 中右侧：控制台流与预览看板 (Bento Workspace Area) - Col span 8 */}
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
            
            {/* Bento Row 2.1: 智能体思考区 (Console Log) */}
            <div className="bg-[#0f172a] rounded-2xl border border-slate-800 shadow-lg shadow-slate-900/10 p-5 flex flex-col gap-3 h-64 overflow-hidden relative">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-indigo-400" />
                  <span className="text-xs font-mono font-semibold text-slate-300">AGENT CONSOLE LOGS</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#f43f5e]" />
                  <span className="w-2 h-2 rounded-full bg-[#eab308]" />
                  <span className="w-2 h-2 rounded-full bg-[#22c55e]" />
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto font-mono text-xs text-slate-300 space-y-2 pr-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                {logs.map((log, index) => {
                  let colorClass = 'text-slate-400';
                  if (log.type === 'success') colorClass = 'text-emerald-400';
                  if (log.type === 'info') colorClass = 'text-indigo-300';
                  if (log.type === 'system') colorClass = 'text-sky-400 font-semibold';
                  if (log.type === 'error') colorClass = 'text-rose-400';

                  return (
                    <div key={index} className="flex gap-2.5 items-start leading-relaxed hover:bg-slate-800/20 py-0.5 rounded transition-colors">
                      <span className="text-[10px] text-slate-600 shrink-0 select-none">{log.time}</span>
                      <span className={`${colorClass} break-all`}>{log.text}</span>
                    </div>
                  );
                })}
                <div ref={terminalEndRef} />
              </div>
            </div>

            {/* Bento Row 2.2: 良率最终成果预览 (Preview Dashboard) */}
            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm shadow-slate-100/50 flex flex-col transition-all duration-300 hover:shadow-md hover:border-slate-200">
              
              {/* 日报成果头部 */}
              <div className="p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                    <FileSpreadsheet className="h-4 w-4" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-slate-950">V3 屏体良率日报.xlsx</h2>
                    <p className="text-xs text-slate-400">智能体大模型综合分析渲染版 05/26成果</p>
                  </div>
                </div>

                {/* 物理下载按钮 */}
                <button
                  disabled={stage !== STAGES.COMPLETED}
                  className={`py-2 px-4 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all duration-300 ${
                    stage === STAGES.COMPLETED
                      ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-700 hover:to-violet-700 shadow-md shadow-indigo-100'
                      : 'bg-slate-50 text-slate-400 border border-slate-100 cursor-not-allowed'
                  }`}
                  onClick={() => alert('下载良率日报 Excel 成功！样式已通过 FontProcessor 完美格式化。')}
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>导出最新日报 (.xlsx)</span>
                </button>
              </div>

              {/* 卡片内部导航 Tabs */}
              <div className="flex border-b border-slate-100 bg-slate-50/40 p-1.5 gap-1">
                {[
                  { key: 'summary', label: '良率总览与 Gap 分析', icon: TrendingUp },
                  { key: 'exceptions', label: '当日异常 (CT 捕获项)', icon: AlertCircle },
                  { key: 'risks', label: '已知风险与释放计划', icon: Layers }
                ].map((tab) => {
                  const IconComp = tab.icon;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-2 py-2 px-3.5 rounded-lg text-xs font-medium transition-all ${
                        activeTab === tab.key
                          ? 'bg-white text-indigo-600 shadow-sm border border-slate-100/50'
                          : 'text-slate-500 hover:text-slate-800'
                      }`}
                    >
                      <IconComp className="h-3.5 w-3.5" />
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* 数据展示容器 */}
              <div className="p-6">
                
                {/* Tab 1: 良率总览 */}
                {activeTab === 'summary' && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50/70">
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">厂别 segment</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">实际良率</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">BP 目标</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">提拉目标</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">当日 Gap</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider w-[40%]">大模型智能归因 (GenAI Content)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-xs">
                        {YIELD_SUMMARY_MOCK.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/40 transition-colors">
                            <td className="py-3.5 px-4 font-semibold text-slate-700">{row.segment}</td>
                            <td className="py-3.5 px-4 text-slate-900 font-mono">{row.actual}</td>
                            <td className="py-3.5 px-4 text-slate-400 font-mono">{row.bpTarget}</td>
                            <td className="py-3.5 px-4 text-slate-400 font-mono">{row.pullUpTarget}</td>
                            <td className="py-3.5 px-4">
                              <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded font-mono font-semibold ${
                                row.status === 'pass' ? 'bg-emerald-50 text-emerald-600' :
                                row.status === 'warning' ? 'bg-amber-50 text-amber-600' :
                                'bg-rose-50 text-rose-600'
                              }`}>
                                {row.status === 'pass' ? '↑' : '↓'} {row.gap}
                              </span>
                            </td>
                            <td className="py-3.5 px-4">
                              <div className="flex items-start gap-1.5 text-slate-500 leading-relaxed bg-slate-50/40 p-2 rounded-lg border border-slate-100/50">
                                <Sparkles className="h-3.5 w-3.5 text-indigo-500 shrink-0 mt-0.5" />
                                <span>{row.reason}</span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Tab 2: 当日异常 */}
                {activeTab === 'exceptions' && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50/70">
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">异常编号</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">发现站点</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">异常项描述</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">严重等级</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider">影响规模</th>
                          <th className="py-3 px-4 text-xs font-semibold text-slate-500 tracking-wider w-[40%]">异常根因与改善方案</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                        {EXCEPTIONS_MOCK.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/40 transition-colors">
                            <td className="py-3.5 px-4 font-mono font-semibold text-indigo-600">{row.id}</td>
                            <td className="py-3.5 px-4 font-medium">{row.site}</td>
                            <td className="py-3.5 px-4 text-slate-900 font-semibold">{row.item}</td>
                            <td className="py-3.5 px-4">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                row.severity === 'High' ? 'bg-rose-50 text-rose-600 border border-rose-100' : 'bg-amber-50 text-amber-600 border border-amber-100'
                              }`}>
                                {row.severity}
                              </span>
                            </td>
                            <td className="py-3.5 px-4 font-mono">{row.count}</td>
                            <td className="py-3.5 px-4 text-slate-500 leading-relaxed bg-slate-50/20 p-2.5 rounded-lg my-1 block border border-slate-100/50">
                              {row.analysis}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Tab 3: 已知风险与释放 */}
                {activeTab === 'risks' && (
                  <div className="flex flex-col gap-4">
                    <div className="p-4 bg-amber-50/30 border border-amber-100 rounded-xl flex items-start gap-3">
                      <Info className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                      <div className="text-xs text-amber-800 leading-relaxed">
                        <strong>风险看板说明</strong>：以下已知异常和高风险项目由智能体从 CT 历史日报和异常挂起池中关联生成。风险品状态变更和改善计划将直接被注入最终导出的日报 Excel 的指定 SHEET。
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {RISKS_MOCK.map((risk, idx) => (
                        <div key={idx} className="border border-slate-100 rounded-xl p-4 flex flex-col gap-3 hover:border-slate-200 hover:shadow-sm transition-all bg-white">
                          <div className="flex items-start justify-between">
                            <span className="text-xs font-bold text-slate-800 leading-tight">{risk.item}</span>
                            <span className="text-[10px] bg-amber-50 text-amber-700 font-semibold px-2 py-0.5 rounded border border-amber-100">
                              {risk.status}
                            </span>
                          </div>
                          
                          <div className="flex flex-col gap-1 text-[11px] border-t border-slate-50 pt-2.5">
                            <div className="flex justify-between">
                              <span className="text-slate-400">影响预测:</span>
                              <span className="text-rose-500 font-medium">{risk.forecast}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">释放计划:</span>
                              <span className="text-slate-600 font-medium">{risk.plan}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            </div>

          </div>

        </div>
      </main>

      {/* ==========================================
          页脚设计 (Premium Minimalist Footer)
         ========================================== */}
      <footer className="border-t border-slate-100 bg-white py-6 px-8 mt-12 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center justify-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <span>智能体核心服务运转正常 (All Systems Operational)</span>
          </div>
          <div>
            <span>© 2026 半导体与显示智能制造工程部</span>
          </div>
        </div>
      </footer>

    </div>
  );
}