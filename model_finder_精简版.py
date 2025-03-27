#!/usr/bin/env python
"""
===== 精简版模型查找器 (Model Finder Lite) =====
功能：检测缺失模型并生成下载链接的轻量级工具
特点：
- 界面简洁，操作直观
- 工作流JSON分析
- Bing搜索生成下载链接
- HTML结果视图
版本：1.0
日期：2024-03-27
维护：模型管理工具集
"""

import os
import sys
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import webbrowser
import csv
import time
from urllib.parse import urlparse, urljoin
import pandas as pd

# 检查DrissionPage是否可用
try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False

# ----- 核心功能：检测缺失文件 -----

def find_missing_models(workflow_file):
    """从工作流文件中提取缺失的模型文件"""
    print(f"分析工作流文件: {workflow_file}")
    
    # 获取工作流文件所在目录
    base_dir = os.path.dirname(os.path.abspath(workflow_file))
    
    # 加载工作流JSON
    try:
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow_json = json.load(f)
    except Exception as e:
        print(f"加载工作流文件时出错: {e}")
        return []
    
    # 查找文件引用
    file_references = []
    model_extensions = ('.safetensors', '.pth', '.ckpt', '.pt', '.bin', '.onnx')
    
    # 处理所有节点
    for node in workflow_json.get('nodes', []):
        node_id = node.get('id')
        node_type = node.get('type', '')
        widgets_values = node.get('widgets_values', [])
        
        # 跳过空的widgets_values
        if not widgets_values:
            continue
        
        # 检查widgets_values中的每个值
        for value in widgets_values:
            if not isinstance(value, str):
                continue
                
            # 对值进行预处理和初步检查
            value = value.strip()
            
            # 跳过空字符串
            if not value:
                continue
            
            # 跳过包含换行符的字符串(真正的文件名不会有换行)
            if '\n' in value or '\r' in value:
                continue
            
            # 简单检查 - 只检查是否有模型文件扩展名
            if any(value.lower().endswith(ext) for ext in model_extensions):
                # 提取文件名（去掉路径）
                if '\\' in value or '/' in value:
                    value = os.path.basename(value.replace('\\', '/'))
                
                # 额外检查 - 确保是单个文件名而不是多行文本
                if len(value.split()) > 3:  # 文件名通常不会超过3个单词
                    continue
                    
                # 确保文件名有扩展名
                name, ext = os.path.splitext(value)
                if not ext or ext.lower() not in model_extensions:
                    continue
                
                file_references.append({
                    'node_id': node_id,
                    'node_type': node_type,
                    'file_path': value
                })
    
    if not file_references:
        print("工作流中未找到文件引用。")
        return []
    
    print(f"在工作流中找到 {len(file_references)} 个模型文件引用。")
    
    # 检查哪些文件缺失
    missing_files = []
    for ref in file_references:
        file_path = ref['file_path']
        
        # 处理不同的路径格式
        paths_to_check = [file_path, os.path.join(base_dir, file_path)]
        
        # 检查文件是否存在于任何可能的路径
        file_exists = any(os.path.exists(p) for p in paths_to_check)
        
        if not file_exists:
            missing_files.append({
                'node_id': ref['node_id'],
                'node_type': ref['node_type'],
                'file_path': file_path
            })
    
    if not missing_files:
        print("\n所有引用的文件都存在！")
        return []
    
    # 统计缺失文件
    print(f"\n缺失模型文件总数: {len(missing_files)}")
    
    # 打印缺失文件列表
    print("\n缺失文件列表:")
    print("-" * 50)
    for i, missing in enumerate(missing_files, 1):
        print(f"{i}. {missing['file_path']}")
    
    return missing_files

def create_csv_file(missing_files, output_file):
    """创建CSV文件保存缺失文件列表"""
    try:
        # 获取文件名（不含扩展名）
        base_name = os.path.splitext(output_file)[0]
        csv_file = f"{base_name}.csv"
        
        # 获取完整路径
        abs_csv_path = os.path.abspath(csv_file)
        
        # 写入CSV文件
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['序号', '节点ID', '节点类型', '文件名']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, missing in enumerate(missing_files, 1):
                writer.writerow({
                    '序号': i,
                    '节点ID': missing['node_id'],
                    '节点类型': missing['node_type'],
                    '文件名': missing['file_path']
                })
        
        print(f"\nCSV文件已保存为: {abs_csv_path}")
        return csv_file
    except Exception as e:
        print(f"\n创建CSV文件时出错: {e}")
        return None

# ----- 核心功能：生成下载链接 -----

def get_mirror_link(original_url):
    """获取Hugging Face的镜像链接"""
    if not original_url or 'huggingface.co' not in original_url:
        return ''
    
    try:
        # 解析URL以确保正确的格式转换
        parsed_url = urlparse(original_url)
        path = parsed_url.path
        
        # 确保路径格式正确（移除/resolve/并替换为对应路径）
        if '/resolve/' in path:
            path = path.replace('/resolve/', '/blob/')
            
        # 构建正确的镜像链接
        mirror_base_url = "https://hf-mirror.com"
        mirror_url = urljoin(mirror_base_url, path)
        
        # 将blob替换回resolve用于下载
        if '/blob/' in mirror_url:
            mirror_url = mirror_url.replace('/blob/', '/resolve/')
            
        return mirror_url
    except Exception as e:
        print(f"构建镜像链接时出错: {e}")
        return ''

def search_model_links(csv_file, status_callback=None, progress_callback=None):
    """使用Bing搜索引擎查找模型下载链接"""
    if not DRISSION_AVAILABLE:
        print("错误: DrissionPage库未安装，无法使用网络搜索功能")
        print("请运行 'pip install DrissionPage' 安装")
        return False
        
    try:
        # 读取CSV文件
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except Exception:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
        
        # 检查必要的列是否存在
        if '文件名' not in df.columns:
            print("错误: CSV文件必须包含'文件名'列")
            return False
        
        # 添加必要的列
        for col in ['下载链接', '镜像链接', '搜索状态']:
            if col not in df.columns:
                print(f"添加缺失列: '{col}'")
                df[col] = ''
        
        # 获取需要处理的关键词列表
        keywords = []
        for index, row in df.iterrows():
            keyword = row['文件名']
            if pd.isna(keyword) or keyword == '':
                continue
                
            # 检查是否已经处理过
            if row['搜索状态'] == '已处理' and row['下载链接']:
                print(f"跳过已处理的关键词: {keyword}")
                continue
                
            keywords.append(keyword)
        
        if not keywords:
            print("没有找到需要处理的关键词")
            return True
            
        print(f"找到 {len(keywords)} 个需要处理的关键词")
        
        # 创建浏览器配置
        print("正在准备浏览器配置...")
        chrome_options = ChromiumOptions()
        
        # 使用默认用户数据目录 - 使用当前用户的Chrome配置
        user_data_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
        if os.path.exists(user_data_dir):
            print(f"使用默认Chrome用户数据目录: {user_data_dir}")
            chrome_options.set_user_data_path(user_data_dir)
        else:
            print("未找到Chrome用户数据目录，将使用临时配置文件")
        
        # 配置其他浏览器参数
        chrome_options.set_argument('--disable-infobars')
        chrome_options.set_argument('--disable-extensions')
        chrome_options.set_argument('--no-sandbox')
        chrome_options.set_argument('--disable-gpu')
        chrome_options.set_argument('--disable-dev-shm-usage')
        
        # 创建浏览器实例
        page = None
        try:
            print("正在初始化浏览器...")
            page = ChromiumPage(chrome_options)
            
            # 处理每个关键词
            for i, keyword in enumerate(keywords):
                print(f"搜索模型 ({i+1}/{len(keywords)}): {keyword}")
                
                # 更新进度
                if progress_callback:
                    progress_callback(i+1, len(keywords))
                
                try:
                    # 搜索重试
                    max_retries = 3
                    search_success = False
                    
                    for retry in range(max_retries):
                        try:
                            # 访问国际版Bing
                            page.get("https://www.bing.com/?setlang=en-US")
                            time.sleep(1)
                            
                            # 获取搜索框元素
                            search_box = page.ele("#sb_form_q")
                            
                            if search_box:
                                # 清空搜索框并输入新的搜索关键词
                                search_box.clear()
                                search_query = f'site:huggingface.co "{keyword}"'
                                
                                # 输入搜索关键词
                                search_box.input(search_query)
                                time.sleep(1)
                                
                                # 提交搜索表单
                                page.run_js("document.querySelector('#sb_form').submit();")
                                time.sleep(1)
                                
                                # 尝试提取搜索结果
                                search_results = page.eles("xpath://*[@id='b_results']//h2/a")
                                
                                if search_results and len(search_results) > 0:
                                    # 获取第一个搜索结果
                                    first_result = search_results[0]
                                    title = first_result.text
                                    original_link = first_result.attr("href")
                                    
                                    print(f"找到搜索结果: {title}")
                                    
                                    if 'huggingface.co' in original_link:
                                        # 在原链接中，如果是blob路径，转换为resolve路径用于下载
                                        if "blob" in original_link:
                                            download_link = original_link.replace("/blob/", "/resolve/")
                                        else:
                                            download_link = original_link
                                            
                                        # 构造镜像链接
                                        mirror_link = get_mirror_link(original_link)
                                        
                                        # 保存结果
                                        row_idx = df.index[df['文件名'] == keyword].tolist()
                                        if row_idx:
                                            idx = row_idx[0]
                                            df.at[idx, '下载链接'] = download_link
                                            df.at[idx, '镜像链接'] = mirror_link
                                            df.at[idx, '搜索状态'] = '已处理'
                                            
                                            print(f"生成下载链接: {download_link}")
                                            print(f"生成镜像链接: {mirror_link}")
                                        
                                        search_success = True
                                        break
                                    else:
                                        print(f"找到结果但不是Hugging Face链接，重试 ({retry+1}/{max_retries})...")
                                        time.sleep(1)
                                else:
                                    print(f"Bing搜索未找到结果，重试 ({retry+1}/{max_retries})...")
                                    time.sleep(1)
                            else:
                                print(f"未找到Bing搜索框，重试 ({retry+1}/{max_retries})...")
                                page.refresh()
                                time.sleep(1)
                                
                        except Exception as e:
                            error_msg = str(e)
                            print(f"搜索过程中出错 ({retry+1}/{max_retries}): {error_msg}")
                            
                            # 检查是否是连接断开错误
                            if "与页面的连接已断开" in error_msg or "连接失败" in error_msg:
                                print("浏览器连接断开，尝试重新创建实例...")
                                try:
                                    if page:
                                        page.quit()
                                except:
                                    pass
                                    
                                time.sleep(1)
                                page = ChromiumPage(chrome_options)
                            
                            time.sleep(1)
                    
                    # 如果搜索失败，标记为未找到
                    if not search_success:
                        print(f"未能找到模型 {keyword} 的下载链接")
                        
                        row_idx = df.index[df['文件名'] == keyword].tolist()
                        if row_idx:
                            idx = row_idx[0]
                            df.at[idx, '搜索状态'] = '未找到'
                    
                    # 每处理一个关键词保存一次进度
                    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                    print(f"已保存当前进度 ({i+1}/{len(keywords)})")
                    
                    # 两次搜索之间增加等待时间
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"处理关键词 {keyword} 时发生错误: {str(e)}")
                    
                    row_idx = df.index[df['文件名'] == keyword].tolist()
                    if row_idx:
                        idx = row_idx[0]
                        df.at[idx, '搜索状态'] = '处理错误'
                    
                    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        finally:
            # 确保浏览器实例被关闭
            if page:
                try:
                    print("正在关闭浏览器...")
                    page.quit()
                except Exception as e:
                    print(f"关闭浏览器时出错: {str(e)}")
        
        # 创建HTML视图
        html_file = create_html_view(csv_file)
        if html_file:
            print(f"已生成HTML结果文件: {html_file}")
            return html_file
        
        return True
    
    except Exception as e:
        print(f"处理CSV文件时发生错误: {str(e)}")
        return False

def create_html_view(csv_file):
    """创建简单的HTML视图"""
    try:
        # 读取CSV文件
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except Exception:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
        
        # 生成HTML文件名
        html_file = os.path.splitext(csv_file)[0] + '.html'
        
        # 创建HTML内容
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>模型下载链接</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                a { text-decoration: none; color: blue; }
                a:hover { text-decoration: underline; }
                .status-processed { color: blue; }
                .status-notfound { color: red; }
                .status-error { color: orange; }
                .file-name { font-weight: bold; }
                .link-col { max-width: 300px; word-break: break-all; }
            </style>
        </head>
        <body>
            <h1>模型下载链接</h1>
            <p style="margin-bottom: 20px;">
                注意：所有链接为通过网络搜索自动生成，查找结果可能不完全准确。
            </p>
            <table>
                <tr>
        """
        
        # 添加表头
        core_columns = ['文件名', '下载链接', '镜像链接', '搜索状态']
        for col in df.columns:
            if col in core_columns or col in ['序号', '节点ID', '节点类型']:
                html_content += f"<th>{col}</th>\n"
        
        html_content += "</tr>\n"
        
        # 添加数据行
        for index, row in df.iterrows():
            html_content += "<tr>\n"
            
            for col in df.columns:
                if col not in core_columns and col not in ['序号', '节点ID', '节点类型']:
                    continue
                    
                value = row.get(col, '')
                if pd.isna(value):
                    value = ''
                    
                if col == '搜索状态':
                    if value == '已处理':
                        status_class = "status-processed"
                    elif value == '处理错误':
                        status_class = "status-error"
                    else:
                        status_class = "status-notfound"
                    html_content += f'<td class="{status_class}">{value}</td>\n'
                elif col == '文件名':
                    html_content += f'<td class="file-name">{value}</td>\n'
                elif col == '下载链接' or col == '镜像链接':
                    if value and not pd.isna(value):
                        html_content += f'<td class="link-col"><a href="{value}" target="_blank">{value}</a></td>\n'
                    else:
                        html_content += f'<td></td>\n'
                else:
                    html_content += f'<td>{value}</td>\n'
            
            html_content += "</tr>\n"
        
        html_content += """
            </table>
            <div style="margin-top: 20px;">
                <h3>使用说明：</h3>
                <ul>
                    <li>优先使用镜像链接下载，速度更快</li>
                    <li>如果镜像链接无效，可尝试原始下载链接</li>
                    <li>状态为"已处理"表示已生成链接，但不保证链接有效</li>
                    <li>状态为"未找到"表示在搜索引擎中未找到对应的模型</li>
                    <li>状态为"处理错误"表示搜索过程中发生错误</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        # 写入HTML文件
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_file
    except Exception as e:
        print(f"创建HTML视图时出错: {e}")
        return None 

# ----- 精简GUI界面 -----

class SimpleModelFinder:
    def __init__(self, root):
        self.root = root
        self.root.title("模型查找器 - 精简版")
        self.root.geometry("600x500")
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 上半部分 - 工作流检测
        ttk.Label(main_frame, text="第一步：检测工作流缺失文件", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        ttk.Label(main_frame, text="工作流文件:").grid(row=1, column=0, sticky="w")
        self.workflow_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.workflow_path, width=50).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="浏览...", command=self.browse_workflow).grid(row=1, column=2, padx=5)
        
        ttk.Button(main_frame, text="分析缺失文件", command=self.analyze_workflow).grid(row=2, column=0, columnspan=3, sticky="w", pady=5)
        
        ttk.Separator(main_frame, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        
        # 下半部分 - 链接生成
        ttk.Label(main_frame, text="第二步：搜索模型下载链接", font=("Arial", 10, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        ttk.Label(main_frame, text="CSV文件:").grid(row=5, column=0, sticky="w")
        self.csv_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.csv_path, width=50).grid(row=5, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="浏览...", command=self.browse_csv).grid(row=5, column=2, padx=5)
        
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=5)
        ttk.Button(search_frame, text="搜索下载链接", command=self.search_links).pack(side=tk.LEFT, padx=(0, 5))
        self.view_html_btn = ttk.Button(search_frame, text="查看结果", command=self.view_html, state=tk.DISABLED)
        self.view_html_btn.pack(side=tk.LEFT)
        
        # 添加进度条
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=5)
        ttk.Label(progress_frame, text="进度:").pack(side=tk.LEFT, padx=(0, 5))
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(main_frame, orient="horizontal").grid(row=8, column=0, columnspan=3, sticky="ew", pady=10)
        
        # 日志区域
        ttk.Label(main_frame, text="处理日志:").grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=10, column=0, columnspan=3, sticky="nsew", pady=(0, 5))
        
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # 使主框架的列可伸缩
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(10, weight=1)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 存储HTML文件路径
        self.html_file_path = None
        
        # 初始化日志
        self.show_welcome_message()
    
    def show_welcome_message(self):
        """显示欢迎消息"""
        welcome_text = "欢迎使用模型查找器精简版\n\n" \
                      "使用方法:\n" \
                      "1. 选择工作流JSON文件并分析\n" \
                      "2. 使用生成的CSV文件搜索下载链接\n" \
                      "3. 查看HTML结果获取下载链接\n"
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, welcome_text)
    
    def update_log(self, message):
        """更新日志显示"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def browse_workflow(self):
        """浏览工作流文件"""
        file_path = filedialog.askopenfilename(
            title="选择工作流JSON文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            self.workflow_path.set(file_path)
    
    def browse_csv(self):
        """浏览CSV文件"""
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if file_path:
            self.csv_path.set(file_path)
            self.view_html_btn.config(state=tk.DISABLED)
    
    def analyze_workflow(self):
        """分析工作流文件"""
        workflow_file = self.workflow_path.get().strip()
        if not workflow_file:
            messagebox.showerror("错误", "请选择工作流JSON文件")
            return
        
        if not os.path.exists(workflow_file):
            messagebox.showerror("错误", "文件不存在")
            return
        
        # 清空日志
        self.log_text.delete(1.0, tk.END)
        self.status_var.set("正在分析...")
        
        # 重定向stdout到Text控件
        class StdoutRedirector:
            def __init__(self, text_widget):
                self.text_widget = text_widget
            
            def write(self, string):
                self.text_widget.insert(tk.END, string)
                self.text_widget.see(tk.END)
                self.text_widget.update_idletasks()
            
            def flush(self):
                pass
        
        old_stdout = sys.stdout
        sys.stdout = StdoutRedirector(self.log_text)
        
        try:
            # 分析工作流
            missing_files = find_missing_models(workflow_file)
            
            if missing_files:
                # 创建CSV文件
                output_file = os.path.basename(workflow_file)
                csv_file = create_csv_file(missing_files, output_file)
                
                if csv_file:
                    # 自动设置CSV路径
                    self.csv_path.set(csv_file)
                    
                    messagebox.showinfo("完成", f"发现 {len(missing_files)} 个缺失文件，已保存到CSV文件")
                    self.status_var.set(f"分析完成: 找到 {len(missing_files)} 个缺失文件")
                
            else:
                messagebox.showinfo("完成", "没有发现缺失文件")
                self.status_var.set("分析完成: 没有缺失文件")
        
        except Exception as e:
            messagebox.showerror("错误", f"分析过程中出错: {str(e)}")
            self.status_var.set("分析失败")
        
        finally:
            # 恢复stdout
            sys.stdout = old_stdout
    
    def search_links(self):
        """搜索模型下载链接"""
        csv_file = self.csv_path.get().strip()
        if not csv_file:
            messagebox.showerror("错误", "请选择CSV文件")
            return
        
        if not os.path.exists(csv_file):
            messagebox.showerror("错误", "文件不存在")
            return
        
        if not DRISSION_AVAILABLE:
            messagebox.showerror("错误", "DrissionPage库未安装，请运行 'pip install DrissionPage' 安装")
            return
        
        # 清空日志
        self.log_text.delete(1.0, tk.END)
        self.status_var.set("搜索中...")
        self.view_html_btn.config(state=tk.DISABLED)
        
        # 重置进度条
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0%")
        
        # 禁用按钮
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.config(state=tk.DISABLED)
        
        # 在单独的线程中执行搜索，避免界面冻结
        def search_thread():
            # 重定向stdout到Text控件
            class StdoutRedirector:
                def __init__(self, text_widget):
                    self.text_widget = text_widget
                
                def write(self, string):
                    self.text_widget.insert(tk.END, string)
                    self.text_widget.see(tk.END)
                    self.text_widget.update_idletasks()
                
                def flush(self):
                    pass
            
            # 更新进度条的回调函数
            def update_progress(current, total):
                if total > 0:
                    percentage = int((current / total) * 100)
                    self.root.after(0, lambda: self.progress_bar.config(value=percentage))
                    self.root.after(0, lambda: self.progress_label.config(text=f"{percentage}%"))
            
            old_stdout = sys.stdout
            sys.stdout = StdoutRedirector(self.log_text)
            
            try:
                result = search_model_links(csv_file, progress_callback=update_progress)
                
                if isinstance(result, str) and os.path.exists(result):
                    self.html_file_path = result
                    self.status_var.set("搜索完成")
                    
                    # 确保进度条显示100%
                    self.root.after(0, lambda: self.progress_bar.config(value=100))
                    self.root.after(0, lambda: self.progress_label.config(text="100%"))
                    
                    # 在主线程中启用HTML查看按钮
                    self.root.after(0, lambda: self.view_html_btn.config(state=tk.NORMAL))
                    self.root.after(0, lambda: messagebox.showinfo("完成", "搜索完成，可以查看HTML结果"))
                else:
                    self.status_var.set("搜索完成，但没有生成HTML结果")
                    self.root.after(0, lambda: messagebox.showinfo("完成", "搜索完成"))
            
            except Exception as e:
                self.status_var.set("搜索失败")
                self.root.after(0, lambda: messagebox.showerror("错误", f"搜索过程中出错: {str(e)}"))
            
            finally:
                # 恢复stdout
                sys.stdout = old_stdout
                
                # 启用按钮
                self.root.after(0, lambda: self.enable_buttons())
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def enable_buttons(self):
        """启用所有按钮"""
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.config(state=tk.NORMAL)
                for grandchild in widget.winfo_children():
                    if isinstance(grandchild, ttk.Frame):
                        for child in grandchild.winfo_children():
                            if isinstance(child, ttk.Button):
                                child.config(state=tk.NORMAL)
    
    def view_html(self):
        """查看HTML结果"""
        if self.html_file_path and os.path.exists(self.html_file_path):
            webbrowser.open(self.html_file_path)
        else:
            # 尝试根据CSV路径推断HTML路径
            csv_file = self.csv_path.get().strip()
            if csv_file:
                html_file = os.path.splitext(csv_file)[0] + '.html'
                if os.path.exists(html_file):
                    webbrowser.open(html_file)
                    return
            
            messagebox.showerror("错误", "HTML结果文件不存在")

# ----- 主函数 -----

def main():
    root = tk.Tk()
    app = SimpleModelFinder(root)
    
    # 设置图标
    try:
        root.iconbitmap("icon.ico")
    except:
        pass
    
    root.mainloop()

if __name__ == "__main__":
    main() 