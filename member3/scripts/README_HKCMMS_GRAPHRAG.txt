HKCMMS GraphRAG 清洗脚本

项目：
基于知识图谱的中医药诊疗智能体
成员 3：GraphRAG

文件：
1. prepare_hkcmms_graphrag.py
   PDF 提取、乱码检测、OCR、清洗、章节识别、文本分块。

2. requirements_hkcmms_graphrag.txt
   Python 依赖。

安装 Python 依赖：
    python -m pip install -r requirements_hkcmms_graphrag.txt

推荐运行：
    python prepare_hkcmms_graphrag.py ^
      --input data\pharmacopoeia\raw\hkcmms\hkcmms_graphrag_selected_33.zip

PowerShell：
    python prepare_hkcmms_graphrag.py `
      --input data/pharmacopoeia/raw/hkcmms/hkcmms_graphrag_selected_33.zip

默认输出：
    data/pharmacopoeia/processed/hkcmms/

GraphRAG 主要入库文件：
    chunks.jsonl

OCR：
- 默认 auto，仅对乱码且正文字符较多的页面执行 OCR。
- PDF 原生文本正常时不需要 OCR。
- vol1、vol2 中部分旧版 PDF 字体映射损坏，需要 Tesseract。
- Windows 常用语言数据名称为 chi_tra 和 eng。
- 可指定：
    --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"

不使用 OCR：
    python prepare_hkcmms_graphrag.py --input <路径> --ocr never

强制重跑：
    python prepare_hkcmms_graphrag.py --input <路径> --force
