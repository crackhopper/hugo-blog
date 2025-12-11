// TOC 收起/展开功能
document.addEventListener('DOMContentLoaded', () => {
    const tocWidget = document.querySelector('.toc-widget');
    const rightSidebar = document.getElementById('right-sidebar');
    const tocFloatBtn = document.getElementById('toc-float-btn');
    
    if (!tocWidget || !rightSidebar) {
        return;
    }
    
    // 切换TOC显示状态的函数
    const toggleTOC = (collapsed: boolean) => {
        const body = document.body;
        if (collapsed) {
            // 收起
            tocWidget.classList.add('collapsed');
            rightSidebar.classList.add('collapsed');
            body.classList.remove('toc-open');
            if (tocFloatBtn) {
                tocFloatBtn.classList.add('collapsed');
            }
            localStorage.setItem('toc-collapsed', 'true');
        } else {
            // 展开
            tocWidget.classList.remove('collapsed');
            rightSidebar.classList.remove('collapsed');
            body.classList.add('toc-open');
            if (tocFloatBtn) {
                tocFloatBtn.classList.remove('collapsed');
            }
            localStorage.setItem('toc-collapsed', 'false');
        }
    };
    
    // 从localStorage读取保存的状态
    const savedState = localStorage.getItem('toc-collapsed');
    if (savedState === 'true') {
        toggleTOC(true);
    } else {
        // 确保初始状态正确
        if (tocFloatBtn) {
            tocFloatBtn.classList.remove('collapsed');
        }
        // 在手机上，初始状态应该是收起的
        if (window.innerWidth < 768) {
            toggleTOC(true);
        }
    }
    
    // 在手机上，点击遮罩层关闭TOC
    // 使用事件委托，点击遮罩层区域时关闭TOC
    document.body.addEventListener('click', (e) => {
        if (window.innerWidth < 768) {
            const target = e.target as HTMLElement;
            const isCollapsed = tocWidget.classList.contains('collapsed');
            // 如果TOC是展开的，且点击的不是右侧边栏或悬浮按钮，则关闭TOC
            if (!isCollapsed && 
                !rightSidebar.contains(target) && 
                target !== tocFloatBtn &&
                !tocFloatBtn?.contains(target)) {
                toggleTOC(true);
                e.stopPropagation();
            }
        }
    });
    
    // 悬浮按钮点击事件 - 双向切换
    if (tocFloatBtn) {
        tocFloatBtn.addEventListener('click', () => {
            const isCollapsed = tocWidget.classList.contains('collapsed');
            toggleTOC(!isCollapsed);
        });
    }
});

