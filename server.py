#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
1. 初始化fastmcp
2. 创建一个函数，文档，功能描述、参数描述、返回值描述
3. 使用@tool 注解
3. 启动 mcp 服务器
"""
import time
from datetime import datetime
import pyautogui
import webbrowser
from fastmcp import FastMCP
import http.client
import json
from Weather_data_get import get_weather
import sys
from read_webpage import read_webpage, extract_current_webpage_url, convert_document_to_txt
from agent_vision import get_image_response
from screen_shot_opencv import capture_screen_opencv_only
from get_active_window import get_activate_path, get_active_window_info, activate_window_by_pid
from open_app import create_and_open_word_doc, open_netease_music
from write_file import ai_write_and_open_txt, ai_write_code_and_open_txt
from summarize_write_ai import code_ai_explain_model, get_file_summary
import pyperclip
from write_file import write_and_open_txt
from control_iflow import use_iflow_in_cmd
from markdown_to_mord_fun import md_to_word, create_file_path, open_word_doc
import subprocess
import os
from dotenv import load_dotenv
from gesture_main_use import main_gesture
from markdown_to_excel import markdown_to_excel_main

load_dotenv()  # 默认会加载根目录下的.env文件

mcp = FastMCP()

@mcp.tool()
def create_or_write_file(file_path: str, content: str) -> str:
    """
    Creates a new file or overwrites an existing file and writes content to it.
    Use this for simple file creation and writing tasks, like creating a 'hello.txt' with 'helloworld' content.

    Args:
        file_path (str): The path of the file to create or write to. Can be a relative or absolute path.
        content (str): The content to write into the file.

    Returns:
        str: A message indicating success or failure.
    """
    try:
        # Ensure the directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"Successfully created or wrote to file at {os.path.abspath(file_path)}"
    except Exception as e:
        return f"Failed to create or write to file. Error: {str(e)}"

@mcp.tool()
def fetch_current_weather_for_city(city: str = None) -> str:
    """
    获取城市天气情况，查询指定城市的当前天气信息
    
    该函数通过和风天气API获取指定城市的当前天气状况，包括温度、湿度、风力等信息。
    如果未指定城市，则默认查询电脑IP所在城市的天气情况。
    
    Args:
        city (str, optional): 城市名称，支持中文城市名，如"北京"、"上海"等。
            默认值为None，此时查询电脑IP所在城市的天气情况。
            
    Returns:
        str: 城市天气情况的详细描述。包含温度、湿度、风力等信息。
    """
    try:
        if city:
            return get_weather(city)
        else:
            return get_weather()
    except Exception as e:
        return f"获取天气信息失败，请检查是否使用正确的和风天气API"


@mcp.tool()
def search_chat(content: str) -> str:
    """
    搜索相关内容并返回答案，在未指定具体网站时用于搜索相关信息，不用于打开网页。
    用AI搜索引擎搜索相关内容。
    
    该函数通过调用 metaso 搜索引擎 API 来搜索指定内容，并返回搜索结果的 JSON 字符串。
    
    Args:
        content (str): 要搜索的查询内容，可以是问题、关键词或短语
        
    Returns:
        str: 搜索结果的 JSON 字符串。
    """
    try:
        conn = http.client.HTTPSConnection("metaso.cn")
        payload = json.dumps({"q": content, "scope": "webpage", "includeSummary": True, "size": "30",
                              "includeRawContent": False, "conciseSnippet": False})
        headers = {
            'Authorization': 'Bearer '+os.getenv("METASO_API_KEY"),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        conn.request("POST", "/api/v1/search", payload, headers)
        res = conn.getresponse()
        data = res.read()
        return data.decode("utf-8")
    except Exception as e:
        return "没有搜索到相关内容"

@mcp.tool()
def search_in_websites(website_names: list, search_contents: list) -> str:
    """
    在指定的多个网站中同时搜索多个内容，支持在常用网站内搜索相关内容
    
    Args:
        website_names (list): 要进行搜索的网站名称列表。
        search_contents (list): 要搜索的内容关键词或短语列表。

    Returns:
        str: 操作结果描述。
    """
    # 网站搜索URL映射字典
    website_search_urls = {
        # ... (dictionary content)
    }
    try:
        if not isinstance(website_names, list) or not isinstance(search_contents, list):
            return "参数错误：website_names 和 search_contents 必须是列表"
        if not search_contents:
            return "搜索内容列表不能为空"
        if not website_names:
            return "网站名称列表不能为空"
        
        successful_searches = []
        failed_sites = []
        
        for website_name in website_names:
            matched = False
            for key, url_template in website_search_urls.items():
                if website_name.lower() in key.lower() or key.lower() in website_name.lower():
                    for search_content in search_contents:
                        try:
                            search_url = url_template.format(search_content)
                            webbrowser.open_new(search_url)
                            successful_searches.append(f"{key}({search_content})")
                        except Exception as e:
                            failed_sites.append(f"{key}({search_content})(打开失败: {str(e)})")
                    matched = True
                    break
            if not matched:
                for search_content in search_contents:
                    failed_sites.append(f"{website_name}({search_content})(不支持的网站)")

        result_message = ""
        if successful_searches:
            result_message += f"已在以下网站中搜索相关内容：{', '.join(successful_searches)}，请查看浏览器结果。"
        if failed_sites:
            result_message += f" 部分搜索失败：{', '.join(failed_sites)}。"
        if not result_message:
            result_message = "没有指定要搜索的网站或内容。"
        return result_message
    except Exception as e:
        return f"在网站中搜索时出错: {str(e)}"

@mcp.tool()
def launch_urls_in_browser(urls: list) -> str:
    """
    打开指定的网址URL列表，支持同时打开多个网址。
    
    Args:
        urls (list): 要打开的网址URL列表，每个URL需要包含完整的协议头（如http://或https://）
        
    Returns:
        str: 操作结果描述。
    """
    try:
        if not isinstance(urls, list):
            return "参数错误：urls 必须是一个网址列表"
        
        valid_urls = [url for url in urls if url.startswith("http://") or url.startswith("https://")]
        invalid_urls = [url for url in urls if url not in valid_urls]
        
        opened_urls = []
        for url in valid_urls:
            try:
                webbrowser.open_new(url)
                opened_urls.append(url)
            except Exception as e:
                invalid_urls.append(f"{url}(打开失败: {str(e)})")
        
        result_message = ""
        if opened_urls:
            result_message += f"已成功打开以下网址: {', '.join(opened_urls)}。"
        if invalid_urls:
            result_message += f" 以下网址格式错误或打开失败: {', '.join(invalid_urls)}。"
        if not result_message:
            result_message = "没有指定要打开的网址。"
        return result_message
    except Exception as e:
        return f"打开网址时出错: {str(e)}"

@mcp.tool()
def open_popular_websites(website_names: list) -> str:
    """
    打开常用网站网页，支持同时打开多个流行网站

    Args:
        website_names (list): 网站名称或关键词列表。

    Returns:
        str: 操作结果描述。
    """
    websites = {
        # ... (dictionary content)
    }
    if not isinstance(website_names, list):
        return "参数错误：website_names 必须是一个网站名称列表"

    successful_sites = []
    failed_sites = []

    try:
        for website_name in website_names:
            url = websites.get(website_name.lower())
            if not url:
                 # Fuzzy matching
                for key, site_url in websites.items():
                    if website_name.lower() in key.lower():
                        url = site_url
                        break
            
            if url:
                webbrowser.open_new(url)
                successful_sites.append(website_name)
            else:
                search_url = f"https://www.bing.com/search?q={website_name}"
                webbrowser.open_new(search_url)
                failed_sites.append(website_name)

        result_message = ""
        if successful_sites:
            result_message += f"已成功打开以下网站: {', '.join(successful_sites)}。"
        if failed_sites:
            result_message += f" 未找到以下网站，已通过搜索引擎查找: {', '.join(failed_sites)}。"
        if not result_message:
            result_message = "没有指定要打开的网站。"
        return result_message
    except Exception as e:
        return f"打开网站时出错: {str(e)}"

@mcp.tool()
def read_and_summary_webpage() -> str:
    """
    总结当前网页内容（除PPT），收到读取网页内容或总结网页内容的指令就执行该命令，不管是否有已打开的网页

    :return: 网页内容摘要
    """
    try:
        summary = read_webpage()
        return_content = get_file_summary(summary)
        pyperclip.copy(return_content)
        write_and_open_txt(return_content, file_path="file_summary\summary.txt")
        return f"已生成总结，文件已保存到：file_summary\summary.txt 并打开，请查看。"
    except Exception as e:
        return f"读取网页内容时出错: {str(e)}"

@mcp.tool()
def identify_current_screen_save_img_and_get_response(user_content: str) -> str:
    """
    识别当前屏幕内容，然后返回识别结果

    :param user_content: 用户关于屏幕内容的问题
    :return: 屏幕识别结果
    """
    try:
        capture_screen_opencv_only("imgs/screen_opencv.png")
        return get_image_response(user_content, "imgs/screen_opencv.png")
    except Exception as e:
        return f"识别当前屏幕时出错: {str(e)}"

@mcp.tool()
def generate_code_from_prompt(user_content: str) -> str:
    """
    写代码。
    :param user_content:
    :return:
    """
    try:
        return_content = ai_write_code_and_open_txt(user_content)
        return f"已生成代码，文件已保存到：file_summary\code.txt 并打开，请查看。"
    except Exception as e:
        return f"写文章时出错: {str(e)}"

@mcp.tool()
def explain_code(user_content: str, code_content: str = None) -> str:
    """
    获取当前代码内容并讲解，解释代码，讲解代码。
    
    Args:
        user_content (str): 用户对代码的特定问题或要求
        code_content (str, optional): 代码内容，如果提供则直接使用，否则从当前活动窗口获取。

    Returns:
        str: 代码解释内容
    """
    try:
        time.sleep(0.1)
        if not code_content:
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.hotkey('ctrl', 'c')
            code_content = pyperclip.paste()
        
        return_content = code_ai_explain_model(code_content + "\n" + user_content)
        write_and_open_txt(return_content, file_path="file_summary\explain.txt")
        return f"已生成代码解释，文件已保存到：file_summary\explain.txt 并打开，请查看。"
    except Exception as e:
        return f"读取代码失败: {str(e)}"

@mcp.tool()
def get_text_content(return_content: bool = False) -> str:
    """
    获取当前文本内容（除PPT）。

    Args:
        return_content (bool, optional): 是否返回文本内容。默认为False。
        
    Returns:
        str: 结果描述或内容。
    """
    try:
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'c')
        text_content = pyperclip.paste()
        txt_file_path = os.path.abspath("file_summary\tempt.txt")
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        if return_content:
            return f"获取的文本已保存到{txt_file_path}文件中，文件内容为：{text_content}"
        else:
            return f"获取的文本已保存到{txt_file_path}文件中。"
    except Exception as e:
        return f"读取文本内容失败: {str(e)}"

@mcp.tool()
def explain_file_content(text_content: str, user_content: str) -> str:
    """
    负责文件内容，使用文本模型生成内容摘要，总结内容，提取内容重点信息，讲解文本内容，分析文本内容等操作。

    Args:
        text_content (str): 需要处理的文本内容或路径。
        user_content (str): 用户对文本内容的具体要求或问题。

    Returns:
        str: 文本处理结果。
    """
    try:
        time.sleep(0.1)
        if os.path.isfile(text_content) and text_content.endswith('.txt'):
            with open(text_content, 'r', encoding='utf-8') as file:
                text_content = file.read()
        
        return_content = get_file_summary(text_content+"/n"+user_content)
        pyperclip.copy(return_content)
        write_and_open_txt(return_content, file_path="file_summary\summary.txt")
        return f"已生成文本摘要，文件路径为：file_summary\summary.txt 已保存并打开。"
    except Exception as e:
        return f"总结文件内容失败: {str(e)}"

@mcp.tool()
def write_articles_and_reports(user_content: str, ai_content: str = '') -> str:
    """
    写文章，写报告，写论文，写说明，写文本。如果之前有进行过搜索或获取文本内容操作，要结合搜索或获取文本内的内容写文稿。

    Args:
        user_content (str): 用户对文章内容的具体要求。
        ai_content (str, optional): AI搜索或从文本中获取到的相关信息。

    Returns:
        str: 操作结果描述。
    """
    try:
        if ai_content:
            user_content += "搜索到的相关信息有： " + ai_content
        return_content = ai_write_and_open_txt(user_content)
        return f"已生成文章，文件已保存到：.file_summary\write.md 并打开，请查看。"
    except Exception as e:
        return f"写文章时出错: {str(e)}"

@mcp.tool()
def control_iflow_agent(user_content: str):
    """
    直接调用agent解决用户问题。直接调用心流AI解决用户问题。当调用该工具时，无需继续调用其他工具。

    :param user_content: 用户对iflow_agent的指令
    :return: iflow_agent的响应
    """
    use_iflow_in_cmd(user_content)
    return "agent解决问题完成。"

@mcp.tool()
def markdown_to_word_server(markdown_content: str = None, md_file_path: str = None) -> str:
    """
    将文本内容或.md/.txt文件转换为Word文档。

    Args:
        markdown_content (str, optional): Markdown格式的文本内容。
        md_file_path (str, optional): .md或.txt文件的路径。

    Returns:
        str: 操作结果描述。
    """
    try:
        if markdown_content:
            final_markdown_text = markdown_content
        elif md_file_path:
            if not os.path.exists(md_file_path):
                return f"指定的文件不存在: {md_file_path}"
            with open(md_file_path, "r", encoding="utf-8") as f:
                final_markdown_text = f.read()
        else:
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.hotkey('ctrl', 'c')
            final_markdown_text = pyperclip.paste()
        
        with open("file_summary\markdown.md", "w", encoding="utf-8") as f:
            f.write(final_markdown_text)

        output_path = create_file_path()
        md_to_word(output_path)
        open_word_doc(output_path)
        return f"已生成Word文档，文件路径为：" + output_path
    except Exception as e:
        return f"转换Markdown到Word时出错: {str(e)}"

@mcp.tool()
def markdown_to_excel_server(markdown_text: str = None) -> str:
    """
    将文本或文件（.md/.txt）转换为Excel文件。

    Args:
        markdown_text (str, optional): 包含表格数据的文本或文件路径。

    Returns:
        str: 操作结果描述。
    """
    try:
        if markdown_text is None:
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.hotkey('ctrl', 'c')
            markdown_text = pyperclip.paste()
        
        if os.path.isfile(markdown_text):
            with open(markdown_text, "r", encoding="utf-8") as f:
                markdown_text = f.read()
        
        output_path = markdown_to_excel_main(markdown_text)
        return "已生成Excel文件，文件路径为：" + output_path
    except Exception as e:
        return f"转换Markdown到Excel时出错: {str(e)}"

@mcp.tool()
def change_word_file(user_content: str) -> str:
    """
    将当前活动窗口的Word文档进行操作。
    
    Args:
        user_content (str): 用户对Word文档的具体操作要求。

    Returns:
        str: 操作结果描述。
    """
    try:
        word_path = get_activate_path()
        if word_path.endswith((".docx", ".doc")):
            user_content = f"文件路径为：{word_path}\n{user_content}\n将修改后的文件存储下来并打开。"
            word_path_folder = os.path.dirname(word_path)
            use_iflow_in_cmd(user_content, word_path_folder)
            return "操作完成。"
        return "当前文件不是Word文件，请检查文件路径。"
    except Exception as e:
        return f"操作Word文档时出错: {str(e)}"

@mcp.tool()
def change_excel_file(user_content: str) -> str:
    """
    将当前活动窗口的Excel文件进行操作。

    Args:
        user_content (str): 用户对Excel文档的具体操作要求。

    Returns:
        str: 操作结果描述。
    """
    try:
        excel_path = get_activate_path()
        if excel_path.endswith((".xlsx", ".xls")):
            user_content = f"文件路径为：{excel_path}\n{user_content}\n将修改后的文件存储下来并打开。"
            excel_path_folder = os.path.dirname(excel_path)
            use_iflow_in_cmd(user_content, excel_path_folder)
            return "操作完成。"
        return "当前文件不是Excel文件，请检查文件路径。"
    except Exception as e:
        return f"操作Excel文档时出错: {str(e)}"

@mcp.tool()
def read_ppt(user_content: str) -> str:
    """
    读取PPT内容并按用户要求进行操作。

    Args:
        user_content (str): 用户对PPT内容的具体操作要求。

    Returns:
        str: 操作结果描述。
    """
    try:
        ppt_path = get_activate_path()
        if ppt_path.endswith((".pptx", ".ppt")):
            pyautogui.hotkey('ctrl', 's')
            result_txt_path = convert_document_to_txt(ppt_path)
            with open(result_txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            os.startfile(ppt_path)
            return_content = get_file_summary(content + "\n" + user_content)
            pyperclip.copy(return_content)
            write_and_open_txt(return_content, file_path="file_summary\summary.txt")
            return f"已生成PPT内容总结，文件已保存到 file_summary\summary.txt 并打开。"
        else:
            return "当前文件不是PPT文件，请检查文件路径。"
    except Exception as e:
        return f"读取PPT时出错: {str(e)}"

@mcp.tool()
def read_pdf(user_content: str) -> str:
    """
    读取PDF内容并按用户要求进行操作。

    Args:
        user_content (str): 用户对PDF内容的具体操作要求。

    Returns:
        str: 操作结果描述。
    """
    try:
        app_name = get_activate_path()
        if app_name in ["msedge.exe", "chrome.exe", "firefox.exe"]:
            pyautogui.hotkey('ctrl', 'l')
            pyautogui.hotkey('ctrl', 'c')
            current_url = pyperclip.paste()

            import urllib.parse
            path_without_scheme = current_url.replace("file://", "")
            decoded_path = urllib.parse.unquote(path_without_scheme)
            if os.name == 'nt' and decoded_path.startswith('/'):
                decoded_path = decoded_path[1:]

            result_txt_path = convert_document_to_txt(decoded_path)
            with open(result_txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return_content = get_file_summary(content + "\n" + user_content)
            pyperclip.copy(return_content)
            write_and_open_txt(return_content, file_path="file_summary\summary.txt")
            return f"已生成PDF内容总结，文件保存到 file_summary\summary.txt 并打开。"
        else:
            return "当前不是PDF文件，请检查文件路径。"
    except Exception as e:
        return f"读取PDF时出错: {str(e)}"

@mcp.tool()
def control_web(user_content: str) -> str:
    """
    控制当前网页内容，对网页进行操作或处理。

    Args:
        user_content (str): 用户对网页的具体操作要求。

    Returns:
        str: 操作结果描述。
    """
    try:
        web_url = extract_current_webpage_url()
        user_content = f"网址为：{web_url}\n{user_content} 可以选择用python脚本实现\n将生成的文件存储到桌面上的一个文件夹中并打开该文件夹。"
        use_iflow_in_cmd(user_content)
        return "操作完成。"
    except Exception as e:
        return f"操作网页时出错: {str(e)}"

@mcp.tool()
def open_folder(folder_path: str) -> str:
    """
    打开文件资源管理器并进入指定的文件夹路径。

    Args:
        folder_path (str): 要打开的文件夹路径。

    Returns:
        str: 操作结果描述。
    """
    try:
        if not os.path.isdir(folder_path):
            return f"文件夹路径不存在或不是一个文件夹: {folder_path}"
        
        os.startfile(folder_path)
        return f"已成功打开文件夹: {folder_path}"
    except Exception as e:
        return f"打开文件夹时出错: {str(e)}"

@mcp.tool()
def open_app(app_names: list) -> str:
    """
    用命令打开软件。

    Args:
        app_names (list): 要打开的软件名称列表。

    Returns:
        str: 执行结果的描述信息。
    """
    supported_apps = {
        'excel': 'excel', 'powerpnt': 'powerpnt', 'powerpoint': 'powerpnt', 'pycharm': 'pycharm',
        'word': 'winword', 'notepad': 'notepad', 'calculator': 'calc', 'cmd': 'cmd',
        'powershell': 'powershell', 'msedge': 'msedge', 'mspaint': 'mspaint',
        'chrome': 'chrome', 'firefox': 'firefox',
    }
    if not isinstance(app_names, list):
        return "参数错误：app_names 必须是一个应用程序名称列表"

    successful_apps, failed_apps = [], []
    for app_name in app_names:
        app_command = supported_apps.get(app_name.lower())
        if not app_command:
            failed_apps.append(f"{app_name}(不支持的应用)")
            continue
        try:
            subprocess.run(["start", app_command], shell=True, check=True)
            successful_apps.append(app_name)
        except Exception as e:
            failed_apps.append(f"{app_name}(启动失败: {e})")

    result_message = ""
    if successful_apps:
        result_message += f"已成功启动以下应用程序: {', '.join(successful_apps)}。"
    if failed_apps:
        result_message += f" 部分应用程序启动失败: {', '.join(failed_apps)}。"
    return result_message or "没有指定要启动的应用程序。"

@mcp.tool()
def open_netease_music_server() -> str:
    """
    打开网易云音乐
    """
    try:
        pyautogui.press('win')
        time.sleep(0.5)
        pyperclip.copy("网易云音乐")
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(1)
        return "操作完成。"
    except Exception as e:
        return f"打开网易云音乐时出错: {str(e)}"

@mcp.tool()
def control_netease(actions: list) -> str:
    """
    控制网易云音乐客户端的播放行为。

    Args:
        actions: 要执行的操作名称列表。
    """
    action_map = {
        'play_pause': ('ctrl', 'alt', 'p'), 'next_song': ('ctrl', 'alt', 'right'),
        'previous_song': ('ctrl', 'alt', 'left'), 'volume_up': ('ctrl', 'alt', 'up'),
        'volume_down': ('ctrl', 'alt', 'down'), 'mini_mode': ('ctrl', 'alt', 'o'),
        'like_song': ('ctrl', 'alt', 'l'), 'lyrics_toggle': ('ctrl', 'alt', 'd'),
    }
    successful_actions, failed_actions = [], []
    for action in actions:
        keys = action_map.get(action)
        if not keys:
            failed_actions.append(f"{action}(不支持的操作)")
            continue
        try:
            pyautogui.hotkey(*keys)
            if action in ['volume_up', 'volume_down']:
                pyautogui.hotkey(*keys)
            successful_actions.append(action)
        except Exception as e:
            failed_actions.append(f"{action}(执行时出错: {e})")
    
    result_message = ""
    if successful_actions:
        result_message += f"已成功执行以下操作: {', '.join(successful_actions)}。"
    if failed_actions:
        result_message += f" 部分操作执行失败: {', '.join(failed_actions)}。"
    return result_message or "没有指定要执行的操作。"

@mcp.tool()
def gesture_control() -> str:
    """
    执行手势控制，启动手势识别
    """
    try:
        current_file = os.path.dirname(os.path.abspath(__file__))
        gesture_path = os.path.join(current_file, "gesture.exe")
        if os.path.exists(gesture_path):
            cmd_command = f'start cmd /k "cd /d {current_file} && gesture.exe"'
            subprocess.Popen(cmd_command, shell=True)
            return "已成功启动手势控制进程。"
        else:
            return "手势控制文件不存在。"
    except Exception as e:
        return f"执行手势操作时出错: {str(e)}"

@mcp.tool()
def stop_gesture_control() -> str:
    """
    关闭手势识别，停止手势控制进程
    """
    try:
        subprocess.run(["taskkill", "/f", "/im", "gesture.exe"], check=True)
        return "已成功关闭手势控制进程。"
    except Exception as e:
        return f"关闭手势控制进程时出错: {str(e)}"

@mcp.tool()
def get_clipboard_content() -> str:
    """
    获取剪切板中的内容并返回
    """
    try:
        return pyperclip.paste() or "剪切板中没有文本内容"
    except Exception as e:
        return f"获取剪切板内容时出错: {str(e)}"

@mcp.tool()
def execute_system_shortcut(actions: list) -> str:
    """
    执行 Windows 系统常用快捷键。

    Args:
        actions (list): 要执行的快捷键操作名称列表。
    """
    shortcuts = {
        # ... (dictionary content)
    }
    if not isinstance(actions, list):
        return "参数错误：actions 必须是快捷键操作名称列表"

    successful_actions, failed_actions = [], []
    
    def handle_special_action(action):
        # ... (function content)
        return False, ""

    for action in actions:
        is_special, special_result = handle_special_action(action)
        if is_special:
            if "出错" not in special_result:
                successful_actions.append(action)
            else:
                failed_actions.append(f"{action}({special_result})")
            continue

        keys = shortcuts.get(action)
        if not keys:
            failed_actions.append(f"{action}(不支持的操作)")
            continue
        try:
            pyautogui.hotkey(*keys)
            successful_actions.append(action)
        except Exception as e:
            failed_actions.append(f"{action}(执行时出错: {e})")

    result_message = ""
    if successful_actions:
        result_message += f"已成功执行以下操作: {', '.join(successful_actions)}。"
    if failed_actions:
        result_message += f" 部分操作执行失败: {', '.join(failed_actions)}。"
    return result_message or "没有指定要执行的操作。"

@mcp.tool()
def create_folders_in_active_directory(folder_names: list) -> str:
    """
    在当前活动文件夹路径下创建多个新文件夹。

    Args:
        folder_names (list): 要创建的文件夹名称列表。
    """
    try:
        if not folder_names:
            return "没有指定要创建的文件夹。"

        active_path = get_activate_path()
        if not os.path.isdir(active_path):
            return f"操作失败：当前活动窗口不是目录文件夹: {active_path}"

        created_folders, existing_folders = [], []
        for folder_name in folder_names:
            new_folder_path = os.path.join(active_path, folder_name)
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
                created_folders.append(folder_name)
            else:
                existing_folders.append(folder_name)

        result_message = ""
        if created_folders:
            result_message += f"已成功创建以下文件夹: {', '.join(created_folders)}。"
        if existing_folders:
            result_message += f" 以下文件夹已存在: {', '.join(existing_folders)}。"
        return result_message
    except Exception as e:
        return f"创建文件夹时出错: {str(e)}"

@mcp.tool()
def open_other_apps(app_names: list) -> str:
    """
    通过Windows开始菜单搜索功能打开软件。

    Args:
        app_names (list): 要启动的软件名称列表。
    """
    try:
        for app_name in app_names:
            pyautogui.press('win')
            time.sleep(0.5)
            pyperclip.copy(app_name)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(1)
        return f"已尝试打开应用: {', '.join(app_names)}"
    except Exception as e:
        return f"打开应用时出错: {str(e)}"

# 服务器运行部分
if __name__ == "__main__":
    mcp.run(transport="http", port=9000)