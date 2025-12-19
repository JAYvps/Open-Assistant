#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import asyncio
import os
import time
from typing import List, Dict
from datetime import datetime
import threading
import base64

from openai import OpenAI
from fastmcp import Client

import json
import re
from dotenv import load_dotenv
import random
from get_active_window import get_activate_path2, get_activate_path

import time
import json
import os
import threading
import queue
import os

# 用于控制悬浮球输入框禁用状态的标志文件路径
INPUT_DISABLE_FLAG = "data/input_disabled.flag"


# REQUEST_ID = "0"
LAST_TIME = 0

# 新增函数：将图片编码为base64
def encode_image(image_path):
    """将图片编码为base64格式"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"图片编码出错: {str(e)}")
        return None

# 新增导入
from server import mcp
from float_ball_line import launch_assistant_avatar

# global keybord_content
#
# keybord_content = None

import argparse
from dotenv import set_key, find_dotenv, dotenv_values

def setup_api_keys():
    """
    Handles API key configuration via command line and interactive prompts.
    Checks for keys, prompts if missing, and allows updating via an argument.
    """
    parser = argparse.ArgumentParser(description="Open Assistant Backend Service")
    parser.add_argument(
        '--update-keys',
        action='store_true',
        help='Force update of API keys even if they already exist.'
    )
    # Parse only known arguments, allowing others to pass through if necessary
    args, _ = parser.parse_known_args()

    env_path = find_dotenv()
    if not os.path.exists(env_path):
        print("No .env file found. Creating a new one.")
        with open(".env", "w") as f:
            pass
        env_path = find_dotenv()

    config = dotenv_values(env_path)

    ali_key = config.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
    metaso_key = config.get("METASO_API_KEY")

    def prompt_for_keys():
        """Interactively prompts user for keys and saves them."""
        print("--- API Key Configuration ---")
        
        new_ali_key = input("请输入您的阿里云API Key (ALIBABA_CLOUD_ACCESS_KEY_ID): ").strip()
        if new_ali_key:
            set_key(env_path, "ALIBABA_CLOUD_ACCESS_KEY_ID", new_ali_key)
            print("...阿里云API Key 已保存。")

        new_metaso_key = input("请输入您的秘塔AI搜索API Key (METASO_API_KEY): ").strip()
        if new_metaso_key:
            set_key(env_path, "METASO_API_KEY", new_metaso_key)
            print("...秘塔AI搜索API Key 已保存。")
        
        print("--- 配置完成 ---")

    if args.update_keys or not ali_key or not metaso_key:
        prompt_for_keys()

# Setup API keys before loading them
setup_api_keys()
load_dotenv()  # Load the .env file for the rest of the application

class AgentServiceHost:
    def __init__(self, script: str, model="qwen-plus", max_tool_calls=1):
        self.script = script
        self.model = model
        self.max_tool_calls = max_tool_calls  # 每个工具的最大调用次数

        self.client = OpenAI(
            # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
            api_key=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        self.session = Client(script)
        self.tools = []
        self.tool_call_count = {}  # 记录每个工具的调用次数
        self.chat_history = []  # 新增：用于存储对话历史

    def read_ai_setting_file(file_path="ai_setting.txt"):
        """
        读取txt文件内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # 读取文件内容
                content = file.read()
                return content
        except FileNotFoundError:
            return "文件未找到"
        except Exception as e:
            return f"读取文件时出错: {str(e)}"

    async def prepare_tools(self):
        tools = await self.session.list_tools()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
            }
            for tool in tools
        ]

    async def chat(self, messages: List[Dict], tool_call_path=None, image_path=None):
        if tool_call_path is None:
            tool_call_path = []  # 记录调用路径，防止重复调用

        if not self.tools:
            await self.prepare_tools()

        content2 = None
        with open("ai_setting.txt", 'r', encoding='utf-8') as file:
            # 读取文件内容
            content2 = file.read()

        # 添加系统消息
        system_message = {
            "role": "system",
            "content": "你是 Open Assistant，一个桌面AI助手。你的首要任务是使用工具来准确地完成用户请求。当用户的指令涉及文件操作、系统控制或网络请求时，必须调用相应的工具。绝不允许自行编造操作结果。在工具调用完成后，你必须根据工具返回的真实结果进行回复。回答要简短有力。"+content2
        }
        #print(system_message)

        # 确保系统消息在消息列表的开头
        if messages and messages[0].get("role") != "system":
            messages = [system_message] + messages
        elif not messages:
            messages = [system_message]

        # 处理多模态和工具调用的混合方案
        if image_path and os.path.exists(image_path):
            # 第一步：使用多模态模型分析图片
            vision_model = "qwen3-vl-flash"
            
            # 编码图片
            base64_image = encode_image(image_path)
            if base64_image:
                # 保存原始消息内容
                original_messages = messages.copy()
                
                # 修改用户消息以包含图片
                for msg in messages:
                    if msg.get("role") == "user":
                        # 创建包含文本和图片的内容
                        msg["content"] = [
                            {
                                "type": "text",
                                "text": msg.get("content", "") + "\n你现在只需要详细描述图片内容，以标准化格式化的方式描述图片内容，比如有表格就用Markdown表格格式描述，以便文本模型进行后续可能的工具调用。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                        break
                
                # 使用视觉模型分析图片
                vision_response = self.client.chat.completions.create(
                    model=vision_model,
                    messages=messages,
                    max_tokens=1024,
                )
                
                # 如果需要工具调用，切换到文本模型
                # 我们需要将视觉模型的分析结果传递给文本模型
                image_analysis = vision_response.choices[0].message.content
                print(f"多模态模型图片分析结果: {image_analysis}")
                
                # 准备文本模型的消息，包含图片分析结果
                text_messages = original_messages.copy()
                # 更新用户消息，添加图片分析结果
                for msg in text_messages:
                    if msg.get("role") == "user":
                        # 确保content是字符串格式
                        original_content = msg.get("content", "")
                        if isinstance(original_content, list):
                            # 如果content是列表（多模态格式），提取文本部分
                            text_parts = [item.get("text", "") for item in original_content if isinstance(item, dict) and item.get("type") == "text"]
                            content_text = " ".join(text_parts)
                        else:
                            content_text = str(original_content)
                        
                        # 如果content_text中存在“请详细描述图片内容，以便后续可能的工具调用。”这句话，就删除
                        text_need_delete = "\n你现在只需要详细描述图片内容，以标准化格式化的方式描述图片内容，比如有表格就用Markdown表格格式描述，以便文本模型进行后续可能的工具调用。"
                        if text_need_delete in content_text:
                            content_text = content_text.replace(text_need_delete, "")

                        msg["content"] = "[图片分析结果]:( " + image_analysis + ")\n"+ "根据图片信息满足用户要求\n" + content_text + "\n不要调用识别图像工具" 
                        print(f"文本模型接收的消息内容: {msg['content']}")
                        break
                
                # 使用文本模型处理，包括工具调用
                model_to_use = self.model
                messages = text_messages
            else:
                # 图片编码失败，使用默认模型
                model_to_use = self.model
        else:
            # 没有图片，直接使用默认模型
            model_to_use = self.model

        # 创建响应（使用文本模型，支持工具调用）
        response = self.client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            tools=self.tools,
            max_tokens=1024,
        )

        if response.choices[0].finish_reason != 'tool_calls':
            return response.choices[0].message

        # 调用工具
        for tool_call in response.choices[0].message.tool_calls:
            tool_name = tool_call.function.name

            # 检查该工具是否已超过最大调用次数
            if tool_name in self.tool_call_count and self.tool_call_count[tool_name] >= self.max_tool_calls:
                # 如果超过限制，返回错误信息给模型
                error_message = f"工具 {tool_name} 已达到最大调用次数限制 ({self.max_tool_calls}次)，无法继续调用。"
                messages.append({
                    'role': 'assistant',
                    'content': error_message
                })
                # 让模型基于错误信息生成回复
                return await self.chat(messages, tool_call_path)

            # 增加工具调用计数
            if tool_name in self.tool_call_count:
                self.tool_call_count[tool_name] += 1
            else:
                self.tool_call_count[tool_name] = 1

            # 检查是否在调用路径中已经存在，防止循环调用
            tool_call_id = f"{tool_name}_{tool_call.function.arguments}"
            if tool_call_id in tool_call_path:
                error_message = f"检测到循环调用 {tool_name}，已阻止重复调用。"
                messages.append({
                    'role': 'assistant',
                    'content': error_message
                })
                return await self.chat(messages, tool_call_path)

            # 添加到调用路径
            tool_call_path.append(tool_call_id)

            # 调用工具
            try:
                result = await self.session.call_tool(tool_name, json.loads(tool_call.function.arguments))
                messages.append({
                    'role': 'assistant',
                    'content': result.content[0].text if result.content else "工具调用完成"
                })
            except Exception as e:
                error_message = f"工具 {tool_name} 调用出错: {str(e)}"
                messages.append({
                    'role': 'assistant',
                    'content': error_message
                })

            return await self.chat(messages, tool_call_path)

        return response

    async def loop(self):
        global LAST_TIME
        num_i = 1




        # 用于进程间通信的文件路径
        INPUT_FILE = "data/input_message.json"
        OUTPUT_FILE = "data/output_message.json"

        # 确保数据目录存在
        def ensure_data_directory():
            if not os.path.exists("data"):
                os.makedirs("data")
        last_input_time = 0

        while True:


            message = None
            screenshot_filename = None
            input_data = None  # 重命名为input_data以避免变量名冲突
        
            # 检查输入文件是否存在且有更新
            if os.path.exists(INPUT_FILE):
                file_time = os.path.getmtime(INPUT_FILE)
                #print(f"上次时间：{LAST_TIME} 当前时间：{time.time()}")
                if file_time > last_input_time:
                    # 如果if time.time()-LAST_TIME>2:就读取文件，否则就直接不读取操作
                    if time.time()-LAST_TIME>2:
                        # 读取输入消息
                        try:
                            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                # 添加调试信息
                                print(f"[调试] 从{INPUT_FILE}读取内容: {repr(content)}")
                                if content:
                                    try:
                                        input_data = json.loads(content)
                                        print(f"[调试] 成功解析JSON: {input_data.get('content', '无内容')}")
                                    except json.JSONDecodeError as e:
                                        print(f"[调试] JSON解析错误: {e}")
                                        # JSON格式错误时，使用默认错误提示
                                        default_json = '{"request_id": "1761143318.5938723", "content": "￥当前出错了，请重新输入。￥", "timestamp": 1761143318.5938723}'
                                        input_data = json.loads(default_json)
                                else:
                                    print(f"[调试] {INPUT_FILE} 文件内容为空")
                                    # 当文件为空时，检查是否有其他进程可能在频繁写入并清空
                                    # 尝试等待一小段时间后再次读取
                                    time.sleep(0.05)
                                    with open(INPUT_FILE, 'r', encoding='utf-8') as f2:
                                        retry_content = f2.read().strip()
                                        if retry_content:
                                            print(f"[调试] 重试读取到内容: {repr(retry_content)}")
                                            input_data = json.loads(retry_content)
                                        else:
                                            # 文件确实为空时，使用默认的错误提示JSON
                                            default_json = '{"request_id": "1761143318.5938723", "content": "￥当前出错了，请重新输入。￥", "timestamp": 1761143318.5938723}'
                                            input_data = json.loads(default_json)
                        except Exception as e:
                            print(f"[调试] 读取文件时发生错误: {e}")
                            # 发生其他错误时，使用默认错误提示
                            current_time1 = time.time()
                            default_json = f'{{"request_id": "{current_time1}", "content": "￥当前出错了，请重新输入。￥", "timestamp": {current_time1}}}'
                            input_data = json.loads(default_json)
                        
                        # 打印接收到的消息和缩略图文件名（如果有）
                        if input_data:  # 检查input_data是否为None
                            message = input_data.get('content', '')
                            screenshot_filename = input_data.get('screenshot_filename', None)
                        else:
                            message = ''
                            screenshot_filename = None
                        #print(f"消息2222: {message}")
                        if screenshot_filename:
                            print(f"接收到缩略图文件名: {screenshot_filename}")
                        
                        # 记录最后读取时间
                        last_input_time = file_time
                        #time.sleep(0.1)
                    else:
                        last_input_time = file_time
        
            #print("测试信息222: ", message)
            if message and message.strip():
                print("message: ",message)
                print("screenshot_filename: ",screenshot_filename)
                img_content = ""
                                                        
                # 只有当接收到有效信息时才执行延时和返回操作
                
                # 重置工具调用计数器（每次用户提问时重置）
                self.tool_call_count = {}

                # 从输入数据中提取消息内容
                message_content = input_data.get('content', '')
                print(f"原始消息: {message_content}")

                # 使用async with self.session上下文管理器来确保客户端连接
                async with self.session:
                    try:
                        # 先延时0.5秒
                        await asyncio.sleep(0.5)
                        current_activate_window = "当前活跃的软件为："+get_activate_path2()+"\n"
                        if get_activate_path() == "":
                            current_file_path = ""
                        else:
                            current_file_path = "当前文件路径为："+get_activate_path()+""
                        current_time = "当前时间为："+datetime.today().strftime('%Y.%m.%d %H时%M分%S秒')+"\n"
                        question = current_time+current_activate_window+current_file_path+ "用户问题：" + message_content
                        
                        # 将新问题添加到历史记录
                        self.chat_history.append({"role": "user", "content": question})

                        # 控制历史记录长度
                        MAX_HISTORY_LEN = 10
                        if len(self.chat_history) > MAX_HISTORY_LEN:
                            self.chat_history = self.chat_history[-MAX_HISTORY_LEN:]
                            
                        # 确定图片路径
                        image_path = None
                        if screenshot_filename and os.path.exists(screenshot_filename):
                            image_path = screenshot_filename
                            print(f"使用指定图片: {image_path}")
                        elif screenshot_filename:
                            # 如果指定的路径不存在，尝试在imgs目录下查找
                            test_image_path = "imgs/test.png"
                            if os.path.exists(test_image_path):
                                image_path = test_image_path
                                print(f"使用默认测试图片: {image_path}")
                        
                        # 调用chat方法，传入包含历史记录的完整消息列表
                        response = await asyncio.wait_for(
                            self.chat(self.chat_history.copy(), image_path=image_path),
                            timeout=120.0  # 120秒超时
                        )
                    except asyncio.TimeoutError:
                        print("请求超时，重新进入循环")
                        response = type('obj', (object,), {'content': '请求超时。'})  # 创建一个具有content属性的对象
                    except Exception as e:
                        print(f"发生错误: {str(e)}")
                        response = type('obj', (object,), {'content': f'处理请求时发生错误: {str(e)}'})  # 创建一个具有content属性的对象
                    
                    # 检查response是否有内容
                    if not hasattr(response, 'content') or response.content is None:
                        response.content = "无响应内容。"
                    else:
                        # 将AI的回复添加到历史记录
                        self.chat_history.append({"role": "assistant", "content": response.content})

                    # 创建响应数据
                    response_data = {
                        'request_id': input_data.get('request_id', ''),
                        'content': "user: "+message_content + "\n\n" + "AI:\n\n" + response.content,
                        'timestamp': time.time()
                    }
                
                    # 写入输出文件
                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(response_data, f, ensure_ascii=False)
                    
                    print(f"已返回响应: {response_data['content']}")
                    LAST_TIME = time.time()
                    
                # except Exception as e:
                #     print(f"发送响应时出错: {e}")
            
            else:
                pass



            #Sprint("循环结束。")

    
    def get_tool_call_stats(self):
        """
        获取工具调用统计信息
        """
        return self.tool_call_count.copy()

    def reset_tool_call_count(self):
        """
        重置所有工具调用计数
        """
        self.tool_call_count = {}

# 新增函数：运行MCP服务器
def run_server():
    mcp.run(transport="http", port=9000)

# 运行悬浮球线程
def run_float_ball():
    launch_assistant_avatar()

async def start_agent_service():
    # 创建并启动服务器线程
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # 设置为守护线程，主程序退出时自动结束
    server_thread.start()

    # 等待服务器启动
    time.sleep(1)

    # 创建并启动悬浮球线程
    float_ball_thread = threading.Thread(target=run_float_ball)
    float_ball_thread.daemon = True  # 设置为守护线程，主程序退出时自动结束
    float_ball_thread.start()

    # 启动客户端
    mcp_client = AgentServiceHost("http://localhost:9000/mcp", max_tool_calls=1)
    await mcp_client.loop()

if __name__ == '__main__':
    asyncio.run(start_agent_service())
