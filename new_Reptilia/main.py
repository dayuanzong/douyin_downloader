#!/usr/bin/env python3
"""
主程序入口 - 针对ask4porn.cc网站的爬虫程序
"""
import asyncio
import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from client import Ask4PornClient
from downloader import Downloader
from enhanced_downloader import EnhancedDownloader
from video_extractor import VideoExtractor
from config import Config

class CrawlerInterface:
    """爬虫用户界面"""
    
    def __init__(self):
        self.config = Config()
        self.client = None
        self.downloader = None
    
    def print_banner(self):
        """打印程序横幅"""
        banner = """
╔══════════════════════════════════════════════════════════════════╗
║                    Ask4Porn 爬虫程序 v2.0                        ║
║                    高质量视频下载工具                             ║
║                                                                  ║
║  功能特性:                                                       ║
║  ✓ Cookie管理支持                                               ║
║  ✓ 最高质量视频选择                                             ║
║  ✓ 广告视频过滤                                                 ║
║  ✓ 单一视频下载                                                 ║
║  ✓ Cloudflare防护绕过                                           ║
╚══════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def print_menu(self):
        """打印菜单"""
        print("\n请选择操作模式:")
        print("1. 下载单个视频（推荐）")
        print("2. 批量下载所有媒体")
        print("3. 使用Playwright视频提取器")
        print("4. 测试连接")
        print("5. 配置设置")
        print("6. 查看帮助")
        print("0. 退出")
    
    async def download_single_video(self):
        """下载单个视频"""
        target_url = input("\n请输入视频页面URL: ").strip()
        if not target_url:
            print("❌ 错误: 必须提供URL")
            return
        
        print(f"\n🔍 正在分析视频页面...")
        
        # 使用优化的客户端获取最佳视频
        best_video = await self.client.get_best_quality_video(target_url)
        
        if not best_video:
            print("❌ 未找到有效视频，可能需要配置Cookie")
            print("💡 提示: 请参考CLOUDFLARE_BYPASS_GUIDE.md获取Cookie")
            return
        
        print(f"\n📹 视频信息:")
        print(f"   标题: {best_video.title}")
        print(f"   分辨率: {best_video.resolution}")
        print(f"   文件大小: {best_video.file_size / 1024 / 1024:.2f} MB")
        print(f"   URL: {best_video.url[:100]}...")
        
        confirm = input("\n是否下载此视频? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消下载")
            return
        
        print(f"\n⬇️  开始下载...")
        success = await self.downloader.download_file(best_video.url, f"video_{best_video.resolution}.mp4")
        
        if success:
            print("✅ 下载完成!")
        else:
            print("❌ 下载失败")
    
    async def download_all_media(self):
        """批量下载所有媒体"""
        target_url = input("\n请输入页面URL: ").strip()
        if not target_url:
            print("❌ 错误: 必须提供URL")
            return
        
        print(f"\n🔍 正在解析页面...")
        media_urls = await self.client.parse_page(target_url)
        
        if not media_urls:
            print("❌ 未找到媒体文件")
            return
        
        print(f"\n📁 找到 {len(media_urls)} 个媒体文件")
        print("⚠️  注意: 批量下载可能会触发反爬机制")
        
        confirm = input("是否继续? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消下载")
            return
        
        print(f"\n⬇️  开始批量下载...")
        success = await self.downloader.download_all(media_urls)
        
        if success:
            print("✅ 批量下载完成!")
        else:
            print("❌ 批量下载失败")
    
    async def playwright_video_extraction(self):
        """使用Playwright视频提取器"""
        target_url = input("\n请输入视频页面URL: ").strip()
        if not target_url:
            print("❌ 错误: 必须提供URL")
            return
        
        print(f"\n🔍 使用Playwright视频提取器分析页面...")
        
        try:
            # 测试网络连接
            print("🔗 测试网络连接...")
            connected = await self.video_extractor.test_connection()
            if not connected:
                print("❌ 网络连接失败")
                return
            
            # 检查Cookie文件
            print("🍪 检查Cookie配置...")
            cookie_exists = await self.video_extractor.check_cookie_file()
            if not cookie_exists:
                print("⚠️  未找到Cookie文件，可能无法访问受保护内容")
                print("💡 提示: 请参考CLOUDFLARE_BYPASS_GUIDE.md获取Cookie")
                use_cookie = input("是否继续? (y/n): ").strip().lower()
                if use_cookie not in ['y', 'yes']:
                    return
            
            # 提取视频信息
            print("📹 提取视频信息...")
            videos = await self.video_extractor.extract_videos(target_url)
            
            if not videos:
                print("❌ 未找到有效视频")
                print("💡 提示: 可能需要配置有效的Cookie")
                return
            
            print(f"\n✅ 找到 {len(videos)} 个视频:")
            for i, video in enumerate(videos, 1):
                print(f"   {i}. {video.title}")
                print(f"      分辨率: {video.resolution}")
                print(f"      文件大小: {video.file_size / 1024 / 1024:.2f} MB")
                print(f"      URL: {video.url[:80]}...")
                print()
            
            # 选择要下载的视频
            if len(videos) == 1:
                selected_video = videos[0]
                print("自动选择唯一视频进行下载")
            else:
                try:
                    choice = input(f"选择要下载的视频 (1-{len(videos)}) 或输入 'a' 下载所有: ").strip().lower()
                    if choice == 'a':
                        selected_videos = videos
                    else:
                        choice_idx = int(choice) - 1
                        if 0 <= choice_idx < len(videos):
                            selected_videos = [videos[choice_idx]]
                        else:
                            print("❌ 无效选择")
                            return
                except ValueError:
                    print("❌ 无效输入")
                    return
            
            # 下载视频
            if isinstance(selected_videos, list):
                print(f"\n⬇️  开始下载 {len(selected_videos)} 个视频...")
                for i, video in enumerate(selected_videos, 1):
                    print(f"下载进度: {i}/{len(selected_videos)}")
                    success = await self.enhanced_downloader.download_video(video)
                    if success:
                        print(f"✅ 视频 {i} 下载完成")
                    else:
                        print(f"❌ 视频 {i} 下载失败")
            else:
                print(f"\n⬇️  开始下载视频...")
                success = await self.enhanced_downloader.download_video(selected_videos)
                if success:
                    print("✅ 下载完成!")
                else:
                    print("❌ 下载失败")
                    
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            print("💡 提示: 请检查网络连接和Cookie配置")
    
    async def test_connection(self):
        """测试连接"""
        print("\n🧪 测试连接...")
        
        # 测试Cookie有效性
        cookie_string = self.client.cookie_manager.get_cookie_string()
        if cookie_string:
            print("✅ Cookie已配置")
            print(f"   长度: {len(cookie_string)} 字符")
        else:
            print("⚠️  未配置Cookie，可能无法访问受保护内容")
        
        # 测试连接
        success = await self.client.test_connection()
        if success:
            print("✅ 连接测试成功")
        else:
            print("❌ 连接测试失败，可能需要Cloudflare验证")
            print("💡 提示: 请参考CLOUDFLARE_BYPASS_GUIDE.md")
    
    def show_config(self):
        """显示配置"""
        print("\n⚙️  当前配置:")
        print(f"   目标网站: {getattr(self.config, 'target_url', '未设置')}")
        print(f"   Cookie文件: {getattr(self.config, 'curl_file_path', '未设置')}")
        print(f"   cf_clearance: {'已设置' if getattr(self.config, 'cf_clearance', None) else '未设置'}")
        print(f"   广告过滤: {'启用' if getattr(self.config, 'enable_ad_filter', True) else '禁用'}")
        print(f"   广告大小阈值: {getattr(self.config, 'ad_video_size_threshold', 10 * 1024 * 1024) / 1024 / 1024:.1f} MB")
        print(f"   最大并发: {getattr(self.config, 'max_concurrent', 1)}")
        print(f"   超时时间: {getattr(self.config, 'timeout', 30)} 秒")
    
    def show_help(self):
        """显示帮助"""
        help_text = """
📖 使用帮助:

1. Cookie配置:
   - 将浏览器中的cURL命令保存为.txt文件
   - 在config.py中设置curl_file_path指向该文件
   - 或者手动设置cf_clearance值

2. 视频质量选择:
   - 程序会自动选择分辨率最高的视频
   - 支持1080p, 720p, 480p, 360p等格式

3. 广告过滤:
   - 自动过滤小于10MB的视频（可能为广告）
   - 可在配置中调整阈值或禁用过滤

4. Cloudflare防护:
   - 如遇到"Just a moment..."页面
   - 请参考CLOUDFLARE_BYPASS_GUIDE.md

5. 故障排除:
   - 检查网络连接
   - 确认Cookie有效性
   - 尝试使用代理
        """
        print(help_text)
    
    async def run(self):
        """运行主程序"""
        self.print_banner()
        
        # 初始化组件
        self.client = Ask4PornClient(self.config)
        self.downloader = Downloader(self.config)
        self.enhanced_downloader = EnhancedDownloader(self.config)
        self.video_extractor = VideoExtractor()
        
        while True:
            try:
                self.print_menu()
                choice = input("\n请选择 (0-6): ").strip()
                
                if choice == '0':
                    print("👋 感谢使用!")
                    break
                elif choice == '1':
                    async with self.client:
                        await self.download_single_video()
                elif choice == '2':
                    async with self.client:
                        await self.download_all_media()
                elif choice == '3':
                    await self.playwright_video_extraction()
                elif choice == '4':
                    async with self.client:
                        await self.test_connection()
                elif choice == '5':
                    self.show_config()
                    try:
                        input("\n按回车键继续...")
                    except EOFError:
                        print("\n检测到EOF，继续运行...")
                elif choice == '6':
                    self.show_help()
                    try:
                        input("\n按回车键继续...")
                    except EOFError:
                        print("\n检测到EOF，继续运行...")
                else:
                    print("❌ 无效选择，请重新输入")
                
            except KeyboardInterrupt:
                print("\n\n👋 程序被用户中断")
                break
            except EOFError:
                print("\n检测到EOF，程序结束")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                try:
                    input("按回车键继续...")
                except EOFError:
                    print("\n检测到EOF，继续运行...")

async def main():
    """主函数"""
    interface = CrawlerInterface()
    await interface.run()

if __name__ == "__main__":
    asyncio.run(main())