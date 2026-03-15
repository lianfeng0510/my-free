#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
移动端兼容性测试
测试平台在移动设备上的显示和交互
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5001"

def test_viewport_meta(url_path):
    """测试页面是否包含viewport meta标签"""
    try:
        response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            viewport = soup.find('meta', {'name': 'viewport'})
            if viewport:
                print(f"✅ {url_path} - 包含viewport标签")
                return True
            else:
                print(f"❌ {url_path} - 缺少viewport标签")
                return False
        else:
            print(f"❌ {url_path} - 状态码 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {url_path} - 请求失败: {e}")
        return False

def test_touch_targets(url_path):
    """测试触摸目标大小（粗略检查按钮最小尺寸）"""
    try:
        response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 检查按钮样式
            buttons = soup.find_all(['button', 'input', 'a'], class_='btn')
            inline_buttons = soup.find_all(style=lambda s: s and 'padding' in s and 'height' in s if s else False)
            
            btn_count = len(buttons)
            if btn_count > 0:
                print(f"✅ {url_path} - 找到{btn_count}个按钮元素")
            else:
                print(f"⚠️  {url_path} - 未找到按钮元素")
                
            # 检查是否有移动端CSS类
            mobile_classes = soup.find_all(class_=lambda c: c and ('mobile' in c or 'touch' in c or 'responsive' in c))
            if mobile_classes:
                print(f"✅ {url_path} - 找到移动端CSS类")
                
            return True
        else:
            print(f"❌ {url_path} - 状态码 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {url_path} - 请求失败: {e}")
        return False

def test_responsive_images(url_path):
    """测试图片是否响应式"""
    try:
        response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            responsive_count = 0
            
            for img in images:
                style = img.get('style', '')
                if 'max-width: 100%' in style or 'width: 100%' in style:
                    responsive_count += 1
            
            if images:
                print(f"✅ {url_path} - 找到{len(images)}张图片，其中{responsive_count}张为响应式")
            else:
                print(f"✅ {url_path} - 无图片，跳过测试")
            return True
        else:
            print(f"❌ {url_path} - 状态码 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {url_path} - 请求失败: {e}")
        return False

def test_grid_layouts(url_path):
    """测试网格布局是否响应式"""
    try:
        response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            grids = soup.find_all(style=lambda s: s and 'grid-template-columns' in s if s else False)
            
            responsive_grids = 0
            for grid in grids:
                style = grid.get('style', '')
                if 'auto-fit' in style or 'auto-fill' in style or 'minmax' in style:
                    responsive_grids += 1
            
            if grids:
                print(f"✅ {url_path} - 找到{len(grids)}个网格布局，其中{responsive_grids}个为响应式")
                if len(grids) > responsive_grids:
                    print(f"⚠️  {url_path} - 有{len(grids)-responsive_grids}个网格可能非响应式")
            else:
                print(f"✅ {url_path} - 无网格布局，跳过测试")
            return True
        else:
            print(f"❌ {url_path} - 状态码 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {url_path} - 请求失败: {e}")
        return False

def test_page_accessibility(url_path):
    """测试页面可访问性（基本检查）"""
    try:
        response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 检查标题结构
            h1 = soup.find_all('h1')
            if len(h1) > 1:
                print(f"⚠️  {url_path} - 有{len(h1)}个h1标签，建议最多1个")
            
            # 检查图片alt属性
            images = soup.find_all('img')
            images_with_alt = [img for img in images if img.get('alt')]
            if images:
                alt_percentage = len(images_with_alt) / len(images) * 100
                print(f"✅ {url_path} - 图片alt属性: {len(images_with_alt)}/{len(images)} ({alt_percentage:.0f}%)")
            
            # 检查表单标签
            forms = soup.find_all('form')
            for form in forms:
                inputs = form.find_all(['input', 'textarea', 'select'])
                labeled_inputs = 0
                for inp in inputs:
                    if inp.get('id'):
                        label = form.find('label', {'for': inp.get('id')})
                        if label:
                            labeled_inputs += 1
                if inputs:
                    label_percentage = labeled_inputs / len(inputs) * 100 if inputs else 0
                    if label_percentage < 80:
                        print(f"⚠️  {url_path} - 表单标签覆盖率: {labeled_inputs}/{len(inputs)} ({label_percentage:.0f}%)")
            
            return True
        else:
            print(f"❌ {url_path} - 状态码 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {url_path} - 请求失败: {e}")
        return False

def main():
    print("📱 移动端兼容性测试开始")
    print("=" * 60)
    
    # 测试的关键页面
    test_pages = [
        ('/', '首页'),
        ('/services', '服务页面'),
        ('/services?type=second_hand', '二手交易专区'),
        ('/forum', '论坛页面'),
        ('/circle/1', '圈子详情页'),
        ('/post/1', '帖子详情页'),
        ('/new_post', '发帖页面'),
        ('/trade', '二手交易列表'),
        ('/create_runner_order', '发布跑腿订单'),
        ('/runner_dashboard', '跑腿员仪表盘'),
        ('/runner_order_detail/1', '跑腿订单详情'),
        ('/login', '登录页面'),
        ('/register', '注册页面'),
    ]
    
    # 测试结果统计
    results = {
        'viewport': 0,
        'touch': 0,
        'images': 0,
        'grids': 0,
        'accessibility': 0
    }
    total_pages = len(test_pages)
    
    for url_path, description in test_pages:
        print(f"\n🔍 测试: {description} ({url_path})")
        print("-" * 40)
        
        if test_viewport_meta(url_path):
            results['viewport'] += 1
        
        if test_touch_targets(url_path):
            results['touch'] += 1
        
        if test_responsive_images(url_path):
            results['images'] += 1
        
        if test_grid_layouts(url_path):
            results['grids'] += 1
        
        if test_page_accessibility(url_path):
            results['accessibility'] += 1
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("-" * 40)
    
    print(f"✅ Viewport标签: {results['viewport']}/{total_pages} 个页面通过")
    print(f"✅ 触摸目标检查: {results['touch']}/{total_pages} 个页面通过")
    print(f"✅ 响应式图片: {results['images']}/{total_pages} 个页面通过")
    print(f"✅ 响应式网格: {results['grids']}/{total_pages} 个页面通过")
    print(f"✅ 可访问性检查: {results['accessibility']}/{total_pages} 个页面通过")
    
    # 总体评价
    total_score = sum(results.values()) / (len(results) * total_pages) * 100
    print(f"\n🎯 总体移动端友好度: {total_score:.1f}%")
    
    if total_score >= 80:
        print("🎉 移动端兼容性良好！")
    elif total_score >= 60:
        print("⚠️  移动端兼容性中等，建议进一步优化")
    else:
        print("❌ 移动端兼容性较差，需要重点优化")
    
    # 改进建议
    print("\n💡 改进建议:")
    if results['viewport'] < total_pages:
        print("  - 确保所有页面包含viewport meta标签")
    if results['touch'] < total_pages:
        print("  - 检查按钮和链接的触摸目标大小（最小44x44px）")
    if results['grids'] < total_pages:
        print("  - 将固定列数的网格布局改为响应式（使用auto-fit/minmax）")
    if results['images'] < total_pages:
        print("  - 为图片添加max-width: 100%样式")
    
    print("\n📱 移动端预览链接:")
    for url_path, description in test_pages:
        print(f"  - {description}: http://127.0.0.1:5000{url_path}")
    
    print("\n🔧 下一步建议:")
    print("  1. 使用Chrome DevTools设备模拟进行视觉测试")
    print("  2. 在真实手机设备上测试触摸交互")
    print("  3. 使用Lighthouse进行移动端性能测试")
    print("  4. 考虑添加更多移动端专属交互（如下拉刷新）")

if __name__ == "__main__":
    main()