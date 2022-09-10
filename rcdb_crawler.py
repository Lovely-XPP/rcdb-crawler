# 导入相关库
import requests
import os, sys, json
from bs4 import BeautifulSoup
import logging
import colorlog
import pandas as pd
import threading


class Crawler():
    def __init__(self, filename='data.xlsx', thread=4, skip_webid=[], fig=False) -> None:
        # 根路径
        self.root = sys.path[0]
        self.data_path = os.path.join(self.root, 'data')
        self.filename = os.path.join(self.root, filename)

        # 用于储存当前webID，解析进度和request线程数设置
        self.No_thread = []
        self.web_id = 0 # 最后一个网页的webid
        self.total = 0 # 总网页数
        self.count = 0 # 解析的有效数据计数
        self.progress = 0 # 解析进度
        self.thread = thread  # 不要超过 16 会被人封ip

        # 是否爬取图片
        self.fig = fig
        self.fig_list = []
        self.fig_save_path = ""

        # 设置对应线程的网站编号
        for i in range(1, thread + 1):
            self.No_thread.append(i)

        # 全局变量，跳过指定的网页id，这里是未知错误的页面跳过(18146-18155)
        self.skip_webid = skip_webid

        # 全局变量，用于request连接设置
        # 请求头信息
        self.header = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36'}
        self.base_url = "https://rcdb.com/"  # 网站地址
        self.request_err_limit = 5  # 超时上限重试次数
        self.request_connection_timeout = 5  # 连接超时，秒
        self.request_read_timeout = 5  # 接收超时，秒

        # 全局变量，用于判断四个中哪些为空，哪些有值
        self.all_cs = []  # classification
        self.all_ty = []  # type
        self.all_de = []  # design
        self.all_sc = []  # scale
        pass



    ''' 设置记录模块，方便观察运行情况 '''
    def start_logging(self) -> None:
        # log 设置
        logging.basicConfig(
            level=20,  # log 显示等级
            # log 显示格式
            format="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",  # log 显示日期格式
            filename=os.path.join(self.root, 'Logs.log'),  # log 文件名
            filemode='a',  # log 文件记录方式
        )
        logger = logging.getLogger()
        console_formatter = colorlog.ColoredFormatter(
            fmt='%(log_color)s' +
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'white',  # cyan white
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            },
        )
        # 标准输出
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(console_formatter)
        logger.addHandler(handler)



    '''初始化：主要用于创建文件夹，获取已经完成的信息以继续爬虫'''
    def initial(self) -> int:
        web_download = 0 # 用于记录下载的网页数
        all_file_id = [] # 用于储存已下载的id，判断下载进度

        # 创建数据文件夹
        if not os.path.exists(self.data_path):
            os.mkdir(os.path.abspath(self.data_path))
        
        # 获取类别信息
        r = requests.get("https://rcdb.com/os.htm?ot=2")
        soup = BeautifulSoup(r.text, 'lxml')
        all_name = ['cs', 'ty', 'de', 'sc']
        for name in all_name:
            data_html = soup.find('select', {'name': name})
            for child in data_html.children:
                text = child.get_text().strip().lower()
                if text == "all":
                    continue
                exec("self.all_" + name + ".append(text)")
        
        # 以最小的缺失文件id - 1作为下载的网页数
        # 储存所有的已下载id
        for file in os.listdir(self.data_path):
            if 'html' not in file:
                continue
            file_id = file.split('.')[0]
            try:
                all_file_id.append(int(file_id))
            # 若是偶遇不是整数的文件名则跳过
            except ValueError:
                continue
        # 存在文件才继续处理
        if len(all_file_id) != 0:
            # 以下算法可以获得不连续的元素，即缺失的文件id
            all_file_id = sorted(all_file_id)
            delection_web = sorted(list(set(range(all_file_id[0], all_file_id[-1]+1))-set(all_file_id)))
            # 如果没有不连续的元素则取最大值为开始id
            if len(delection_web) == 0:
                web_download = max(all_file_id)
            else:
                # 剔除跳过的缺失文件id
                while delection_web[0] in self.skip_webid:
                    delection_web.pop(0)
                    if len(delection_web) == 0:
                        break
                # 如果缺失个数小于2倍线程数，则取id的最大值，即认为缺失文件较少可以通过后面的检查进行修补，避免冗余
                # 否则取对应2倍线程数索引的缺失文件id - 1
                if len(delection_web) <= 2*self.thread:
                    web_download = max(all_file_id)
                else:
                    web_download = delection_web[2*self.thread-1] - 1
        
        # 如果excel文件存在则判断解析进度，无excel文件则取0
        if os.path.exists(self.filename):
            pd_data = pd.read_excel(self.filename, sheet_name="data")
            count = pd_data.shape[0]
            pd_data = pd.read_excel(self.filename, sheet_name="static")
            static = pd_data.to_dict()
            static = static['webs']
            static = static[0]
        else:
            static = 0
            count = 0
        
        # 赋值
        self.count = count
        self.web_id = web_download  # webid 为最后一个网站编号
        self.total = web_download  
        self.progress = static + 1

        # 为了构造每个线程，需要找到最新的基数
        base = web_download // self.thread
        # total 计数需要减掉跳过的部分
        all_fileid = range(1, self.total+1)
        for item in self.skip_webid:
            if item in all_fileid:
                self.total -= 1
        # 计算每个线程的开始网站id
        i = 0
        for item in self.No_thread:
            self.No_thread[i] = self.thread * base + item
            i += 1
        
        # 输出数据
        if self.total == 0:
            logging.warning("未找到已有数据,程序将重新开始爬取!")
        else:
            if self.progress == 1:
                logging.info("已储存的网站数据: " + str(self.total) + " 个.")



    ''' 解析网站 '''
    def get_data(self, soup: BeautifulSoup, No: int) -> dict:
        # 初始化字典用于储存数据
        data = {}

        # 保存网址编号
        data['webID'] = No

        # 名字和地区
        # 找到feature项
        feature = soup.find("div", {"id": "feature"})
        # 第一个div类包含名字和地区
        name_div = feature.find("div")
        # h1放置名字其他为地区
        name = name_div.find("h1").get_text().strip()
        location = name_div.get_text().replace(name, '')
        data['name'] = name
        data['location'] = location

        # 时间
        # time = feature.find("time").get_attribute_list('datetime')
        # data['time'] = time[0]

        # 分类-种类-设计-恐怖级别
        category = []
        category_html = feature.find('ul')
        # 没找到就不是游乐场类
        if category_html is None:
            logging.warning("网站编号: " + str(No) + ", 类型: People, 不储存信息")
            return {}
        for child in category_html.children:
            text = child.get_text().strip()
            category.append(text)
        # 对关键词分类
        data['classification'] = ""
        data['type'] = ""
        data['design'] = ""
        data['scale'] = ""
        count = 0
        for item in category:
            if item.lower() in self.all_cs:
                data['classification'] = item
                count += 1
                continue
            if item.lower() in self.all_ty:
                data['type'] = item
                count += 1
                continue
            if item.lower() in self.all_de:
                data['design'] = item
                count += 1
                continue
            if item.lower() in self.all_sc:
                data['scale'] = item
                count += 1
                continue
        # 如果所有关键词都对不上，说明不是过山车
        if count == 0:
            logging.warning("网站编号: " + str(No) + ", 类型: Park, 不储存信息")
            return {}
        if count != len(category):
            logging.error("关键词分类后数目与网站不统一,请手动检查!")

        # 更细化种类
        category = ""
        judge = []
        category_html = category_html.find_next_sibling('ul')
        if category_html is not None:
            for child in category_html.children:
                text = child.get_text().strip()
                category = category + ", " + text
                judge.append(text.lower())
        if ("pictures" in judge) or ("maps" in judge) or ("parks nearby" in judge):
            category = ""
        category = category.replace(", ", "", 1)
        data['category'] = category


        # 轨道数据：轨道布局，高度，长度，速度，落差，反转数，垂直角，持续时间
        track_html = feature.find_next('h3', string="Tracks")
        data_names = ["Elements", "Height", "Length", "Speed", "Drop", "Inversions", "Vertical Angle", "Duration"]
        ft_remove_data = ["Height", "Length", "Drop"]
        for data_name in data_names:
            # 没找到就全部参数赋空字符
            if track_html is None:
                data[data_name.lower()] = ""
                continue
            # 找到就赋对应的找到的字符
            text = ""
            track_data = track_html.find_next('th', string=data_name)
            # 找不到一样赋空字符
            if track_data is None:
                data[data_name.lower()] = ""
                continue
            # 合并多个子项
            for entry in track_data.next_siblings:
                # 由于elements可能有多个条目，需要单独列出
                if data_name == "Elements":
                    text_tmp = ""
                    for child in entry.find_all('a'):
                        text_tmp = text_tmp + "," + child.get_text().strip()
                    text_tmp = text_tmp.replace(",", "", 1)
                    text_tmp = text_tmp.strip(",")
                    text = text + " / " + text_tmp
                    continue
                text = text + " / " + entry.get_text().strip()
            # 去除 ft （英寸，长度）单位
            if data_name in ft_remove_data:
                text = text.replace(" ft", "")
            # 去除 mph （英里每小时，速度）单位
            if data_name == "Speed":
                text = text.replace(" mph", "")
            text = text.replace(' / ', '', 1)
            text = text.strip(' / ')
            data[data_name.lower()] = text
        

        # 列车数据：Arrangement 约束装置
        train_html = feature.find_next('h3', string="Trains")
        data_names = ["Arrangement", "Restraints"]
        for data_name in data_names:
            if train_html is None:
                data[data_name.lower()] = ""
                continue
            train_data = train_html.find_next('th', string=data_name)
            if train_data is None:
                data[data_name.lower()] = ""
                continue
            text = train_data.next_sibling.get_text().strip()
            data[data_name.lower()] = text


        # 细节：最大运载能力
        detail_html = feature.find_next('h3', string="Details")
        data_names = ["Capacity"]
        for data_name in data_names:
            if detail_html is None:
                data[data_name.lower()] = ""
                continue
            detail_data = detail_html.find_next('th', string=data_name)
            if detail_data is None:
                data[data_name.lower()] = ""
                continue
            text = detail_data.next_sibling.get_text().strip()
            # 客容量只取数字部分，需要单独处理
            if data_name == "Capacity":
                # 只取数字部分
                text = text.split(' ')
                text = text[0]
                # 删除数字的间隔符
                text = text.replace(',', '')
            data[data_name.lower()] = text

        return data
        


    '''请求html'''
    def request_data(self, thread_id: int) -> None: 
        # 超时计数，大于规定的次数就结束程序
        request_err_count = 0
        try:
            logging.warning("网站Request线程 " + str(thread_id+1) + " 已启动!")
            while True:
                # 跳过指定的页面
                if self.No_thread[thread_id] in self.skip_webid:
                    logging.warning("网站编号: " + str(self.No_thread[thread_id]) + ", 跳过")
                    self.No_thread[thread_id] += self.thread
                    continue

                # 获取网站内容
                url = self.base_url + str(self.No_thread[thread_id]) + ".htm"
                # 请求链接获取html
                try:
                    r = requests.get(url, headers=self.header, timeout=(
                        self.request_connection_timeout, self.request_read_timeout))
                    # 200为正常获取，400为网页不存在即结束，除此之外均认为是网络问题
                    if r.status_code != 200:
                        if r.status_code == 400:
                            logging.warning("网站Request线程 " + str(thread_id+1) + " 已结束!")
                            break
                        logging.warning(
                            "网络可能出现故障，正在重新获取编号为 " + str(self.No_thread[thread_id]) + " 的网站...")
                        continue
                # 用户 crtl + c 终止程序
                except KeyboardInterrupt:
                    logging.error("用户已手动终止程序!")
                    sys.exit()
                # 连接超时重新尝试
                except:
                    logging.warning("网络连接超时，正在重新获取编号为 " +
                                    str(self.No_thread[thread_id]) + " 的网站...")
                    request_err_count += 1
                    # 超时过多就退出程序
                    if request_err_count > self.request_err_limit:
                        logging.error("网络连接超时次数过多，程序已退出!")
                        sys.exit()
                    continue
                # 错误计数重置
                request_err_count = 0

                # 写入当地文件
                data_file = os.path.join(self.data_path, str(self.No_thread[thread_id]) + ".html")
                with open(data_file, 'w') as f:
                    f.write(r.text)
                
                # 显示信息
                logging.info(
                    "网站编号: " + str(self.No_thread[thread_id]) + ", 已储存到本地html!")
                self.No_thread[thread_id] += self.thread

        # 用户 crtl + c 终止程序
        except KeyboardInterrupt:
            logging.error("用户已手动终止程序!")
            exit()



    '''多线程运行requests'''
    def multiple_thread_get_data(self):
        # 多线程同时运行
        for i in range(self.thread):
            exec("thread" + str(i) +
                    " = threading.Thread(target=self.request_data, args=(" + str(i) + ",))")
        for i in range(self.thread):
            exec("thread" + str(i) + ".start()")
        for i in range(self.thread):
            exec("thread" + str(i) + ".join()")
        # 计算总网页数
        self.web_id = max(self.No_thread) - self.thread
        self.total = max(self.No_thread) - self.thread - len(self.skip_webid)


    '''检查下载数据完整性并修复'''
    def check_fix_download_data(self) -> None:
        # 缺失文件id保存列表
        fix_up = []

        # 遍历data文件夹，检查不连续的id并储存到缺失文件列表
        files = os.listdir(self.data_path)
        for i in range(1, self.web_id):
            file = str(i) + '.html'
            # 如果id连续或在跳过的网站内则继续
            if file in files or i in self.skip_webid:
                continue
            fix_up.append(i)
        # 计算缺失文件id数目
        fix_count = len(fix_up)
        fix_id = 0
        # 如果缺失文件id数目大于0则进入修补程序
        if fix_count > 0:
            logging.warning("下载的数据共有 " + str(fix_count) + " 个网站缺失，正在修补...")
            # 遍历缺失文件id进行修补
            for i in fix_up:
                fix_id += 1
                url = self.base_url + str(i) + ".htm"
                while True:
                    try:
                        r = requests.get(url, headers=self.header,
                            timeout=(self.request_connection_timeout, self.request_read_timeout))
                    except KeyboardInterrupt:
                        logging.error("用户已手动终止程序!")
                        exit()
                    except:
                        logging.warning("网络连接超时，正在重新获取编号为 " +
                                        str(i) + " 的网站...")
                        continue
                    data_file = os.path.join(self.data_path, str(i) + ".html")
                    with open(os.path.abspath(data_file), 'w') as f:
                        f.write(r.text)
                    break
                logging.info("网站编号: " + str(i) + ", 已储存到本地html! [修复进度: "
                            + str(round(fix_id/float(fix_count)*100.0, 2))
                            + "% (" + str(fix_id) + "/" + str(fix_count) + ")]")



    '''保存数据'''
    def save_data(self, datas: dict) -> None:
        pd_data = pd.DataFrame(datas)
        # 判断文件是否存在，不存在则创建，存在则读取，以增量形式写入
        if not os.path.exists(self.filename):
            pd_data.to_excel(self.filename, sheet_name="data", index=False)
        else:
            pd_data_ori = pd.read_excel(self.filename)
            pd_data_ori.fillna('')
            pd_data = pd.concat([pd_data_ori, pd_data], ignore_index=True)
            pd_data.to_excel(self.filename, sheet_name="data", index=False)
        static = {'webs': [self.progress]}
        pd_data = pd.DataFrame(static)
        # 写入当前进度
        with pd.ExcelWriter(self.filename, mode='a', engine="openpyxl") as writer:
            pd_data.to_excel(writer, sheet_name="static", index=False)



    '''解析转换数据'''
    def analyze_datas(self) -> int:
        # 有效数据计数
        data_count = 0
        # 用于储存数据
        datas = {}

        # 字典键与excel表头对应的字典
        name_dict = {
            "webID": "ID",
            "name": "名字",
            "location": "地点",
            "classification": "类别",
            "type": "材料",
            "design": "设计",
            "scale": "恐怖程度",
            "category": "细化种类",
            "elements": "设计元素",
            "height": "高度 ft",
            "length": "长度 ft",
            "speed": "速度 mph",
            "drop": "落差 ft",
            "inversions": "反转数",
            "vertical angle": "垂直下落角度",
            "duration": "单次运行时长",
            "arrangement": "Arrangment",
            "restraints": "约束装置",
            "capacity": "每小时载客量"
        }
        
        for self.progress in range(self.progress, self.web_id + 1):
            # 跳过指定的页面
            if self.progress in self.skip_webid:
                logging.warning("网站编号: " + str(self.progress) + ", 跳过")
                continue

            # 打开并解析文件内容
            html_name = os.path.join(self.data_path, str(self.progress) + ".html")
            with open(html_name, 'r') as f:
                content = f.read()
                soup_obj = BeautifulSoup(content, 'lxml')

            # 解析网站内容
            # 获取数据
            data = self.get_data(soup_obj, self.progress)
            if len(data) == 0:
                continue
            # 计数
            total = len(data.keys())
            non_empty = 0
            for key in data.keys():
                if data[key] != '':
                    non_empty += 1
            logging.info("网站编号: " + str(self.progress) + ", 类型: 过山车, 条目数(有效/总数): " +
                            str(non_empty) + "/" + str(total) + ", 数据已储存！")
            data_count += 1

            # 添加数据
            for key in data.keys():
                try:
                    datas[name_dict[key]].append(data[key])
                except:
                    datas[name_dict[key]] = [data[key]]

            # 每5000次保存一次数据
            if self.progress % 5000 == 0:
                self.save_data(datas)
                datas = {}
                # 显示完成信息
                logging.info("解析已完成 " + str(round(self.progress/(self.web_id-1.0)*100.0, 2)) + "% : " +
                             str(self.progress) + "/" + str(self.web_id-1) + ",自动保存成功! ")
        
        # 全部完成需要保存数据
        self.save_data(datas)

        return data_count
    


    '''抓取图片'''
    def get_fig(self, thread_id):
        while True:
            # 查看是否超过索引范围
            try:
                fig = self.fig_list[self.No_thread[thread_id]]
            except IndexError:
                break
                
            # 获取图片网址
            fig_id = fig['id']
            fig_url = fig['url'].replace('/', '')
            fig_url = self.base_url + fig_url

            # 连接超时计数
            request_err_count = 0
            try:
                fig_r = requests.get(fig_url, headers=self.header, timeout=(
                    self.request_connection_timeout, self.request_read_timeout))
            # 用户 crtl + c 终止程序
            except KeyboardInterrupt:
                logging.error("用户已手动终止程序!")
                sys.exit()
            # 连接超时重新尝试
            except:
                logging.warning("网络连接超时，正在重新爬取图片...")
                request_err_count += 1
                # 超时过多就退出程序
                if request_err_count > self.request_err_limit:
                    logging.error("网络连接超时次数过多，程序已退出!")
                    sys.exit()
                continue
            
            # 保存图片到本地
            fig_name = os.path.abspath(os.path.join(self.fig_save_path, str(self.No_thread[thread_id]) + '.jpeg'))
            with open(fig_name, 'wb') as f:
                f.write(fig_r.content)
            self.No_thread[thread_id] += self.thread
            


    '''多线程抓取图片'''
    def multiple_thread_get_fig(self, thread=4):
        # 图片存取路径
        fig_dir = os.path.abspath(os.path.join(self.root, 'fig'))
        # 不存在则新建
        if not os.path.exists(fig_dir):
            os.mkdir(fig_dir)
        
        # 初始化
        # 读取图片进度
        fig_progress = 0
        for file_dir in os.listdir(fig_dir):
            try:
                tmp = int(file_dir)
                if tmp > fig_progress:
                    fig_progress = tmp
            except ValueError:
                continue
        # 如果为0则从1开始，否则就从读取到的最后id开始
        if fig_progress == 0:
            fig_progress = 1
            logging.warning("没有检测到已储存图片的 WebID ,将重新开始爬取图片")
        else:
            logging.info("检测到已储存图片的 WebID 共有 " + str(fig_progress - 1) + " 个")
        logging.info("图片爬虫程序初始化完成, 程序开始运行")
        
        # 开始遍历所有网站
        for progress in range(fig_progress, self.web_id + 1):
            # 跳过指定的页面
            if progress in self.skip_webid:
                logging.warning("网站编号: " + str(progress) + ", 跳过")
                continue
            
            # 打开html
            html_name = os.path.join(self.data_path, str(progress) + ".html")
            with open(html_name, 'r') as f:
                content = f.read()
                soup_obj = BeautifulSoup(content, 'lxml')
            
            # 跳过非过山车的项目
            # 找到feature项
            feature = soup_obj.find("div", {"id": "feature"})
            category = []
            category_html = feature.find('ul')
            # 没找到就不是游乐场类
            if category_html is None:
                logging.warning("网站编号: " + str(fig_progress) + ", 类型: People, 不储存图片")
                continue
            for child in category_html.children:
                text = child.get_text().strip()
                category.append(text)
            count = 0
            for item in category:
                if item.lower() in self.all_cs:
                    count += 1
                    continue
                if item.lower() in self.all_ty:
                    count += 1
                    continue
                if item.lower() in self.all_de:
                    count += 1
                    continue
                if item.lower() in self.all_sc:
                    count += 1
                    continue
            # 如果所有关键词都对不上，说明不是过山车
            if count == 0:
                logging.warning("网站编号: " + str(fig_progress) + ", 类型: Park, 不储存图片")
                continue

            # 建立对应WebID的图片存储文件夹
            webid_path = os.path.abspath(os.path.join(self.root, "fig/" + str(progress)))
            if not os.path.exists(webid_path):
                os.mkdir(webid_path)
            self.fig_save_path = webid_path
            
            # 获取图片列表
            fig_dict_ori = soup_obj.find('script', {'id': 'pic_json'})
            if fig_dict_ori is None:
                continue
            fig_dict = json.loads(fig_dict_ori.get_text().strip())
            self.fig_list = fig_dict['pictures']

            # 如果图片列表比指定的线程数还少，线程数降为图片列表长度
            fig_count = len(self.fig_list)
            if fig_count < thread:
                self.thread = fig_count
            else:
                self.thread = thread

            # 多线程同时运行
            # 设置对应线程的网站编号
            self.No_thread = []
            for i in range(1, self.thread + 1):
                self.No_thread.append(i)
            # 开始运行
            for i in range(self.thread):
                exec("thread" + str(i) +
                    " = threading.Thread(target=self.get_fig, args=(" + str(i) + ",))")
            for i in range(self.thread):
                exec("thread" + str(i) + ".start()")
            for i in range(self.thread):
                exec("thread" + str(i) + ".join()")
            # 输出信息
            logging.info("网站编号: " + str(progress) + ", 类型: 过山车, 图片数目: " +
                         str(len(os.listdir(self.fig_save_path))) + ", 图片已储存！")



    ''' 主函数 '''
    def main(self):
        # 开启记录模块
        self.start_logging()

        # 初始化
        logging.info("程序正在初始化...")
        self.initial()
        logging.info("程序初始化完成!")
        logging.warning("爬虫程序已经开始运行!")
        logging.warning("启用线程数: " + str(self.thread))

        try:
            # 利用多线程抓取网页到本地
            if self.progress == 1:
                self.multiple_thread_get_data()
            
            # 如果进度比总的少则继续分析，否则结束分析
            if self.progress < self.web_id:
                # 检查下载数据完整性，不完整则自动修复
                logging.info("正在检查下载的数据是否完整...")
                self.check_fix_download_data()
                logging.info("检查完成,已下载的网站数据完整!")
                logging.info("已储存的网站数据: " + str(self.total) + " 个, 已经全部储存!")

                # 分析下载的网页数据得到最终的数据
                logging.info("已分析的网站数据: " + str(self.progress-1)
                            + " 个, 有效数据(过山车): " +  str(self.count) + " 个")
                logging.warning("开始分析已储存的网站数据")
                data_count = self.analyze_datas()
                data_count = data_count + self.count
            else:
                data_count = self.count

            # 完成输出
            logging.info("全部数据解析并保存成功, 网页数目: " + str(self.total) +
                        " 个, 有效数据: " + str(data_count) + " 条.")

            if self.fig:
                logging.warning("已开启爬取图片模式，开始初始化爬取图片程序...")
                self.multiple_thread_get_fig(thread=self.thread)
                logging.info("已爬取所有过山车类型网站的图片")

        except KeyboardInterrupt:
            logging.error("用户已手动终止程序!")
            exit()
        
        logging.warning("爬虫程序已结束并退出!")
