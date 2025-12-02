/* eslint-disable */
// deno-lint-ignore-file
// @ts-nocheck: 模板文件

// 这个文件的改动要重新重启，build。才生效。

// 调整这里的毫秒数：数值越小，滚动越快。推荐值 200 - 400。
const SCROLL_DURATION = 300;

// 缓动函数：二次方缓入缓出 (用于平滑加速/减速)
function easeInOutQuad(t: number, b: number, c: number, d: number): number {
  t /= d / 2;
  if (t < 1) return c / 2 * t * t + b;
  t--;
  return -c / 2 * (t * (t - 2) - 1) + b;
}

// 自定义平滑滚动函数 (使用 requestAnimationFrame 实现可控持续时间的平滑滚动)
function customSmoothScroll(targetOffset: number, duration: number) {
  const startPosition = window.pageYOffset;
  const distance = targetOffset - startPosition;
  let startTime: number | null = null;

  function animation(currentTime: number) {
    if (startTime === null) startTime = currentTime;
    const timeElapsed = currentTime - startTime;

    // 如果时间超过了持续时间，直接跳到终点并停止
    if (timeElapsed >= duration) {
      window.scrollTo(0, targetOffset);
      return;
    }

    const run = easeInOutQuad(timeElapsed, startPosition, distance, duration);
    window.scrollTo(0, run);
    window.requestAnimationFrame(animation);
  }

  window.requestAnimationFrame(animation);
}

const anchorLinksQuery = "a[href]";

function setupSmoothAnchors() {
  document.querySelectorAll(anchorLinksQuery).forEach(aElement => {
    let href = aElement.getAttribute("href");
    if (!href.startsWith("#")) {
      return;
    }
    aElement.addEventListener("click", clickEvent => {
      clickEvent.preventDefault();

      const targetId = decodeURI(aElement.getAttribute("href").substring(1)),
        target = document.getElementById(targetId) as HTMLElement,
        // 计算目标偏移量
        offset = target.getBoundingClientRect().top - document.documentElement.getBoundingClientRect().top;

      const targetAbsoluteTop = target.getBoundingClientRect().top + window.pageYOffset;        
      const targetOffset = targetAbsoluteTop;
      // const targetOffset = targetAbsoluteTop - (document.querySelector('.fixed-header')?.offsetHeight || 0);

      window.history.pushState({}, "", aElement.getAttribute("href"));

      customSmoothScroll(targetOffset, SCROLL_DURATION);

      // ----------------------------------------------------------------------
      //  瞬间跳转 (将 behavior 设置为 "auto")
      // ----------------------------------------------------------------------
      // scrollTo({
      //   top: offset,
      //   behavior: "auto" // 瞬间跳转
      // });

      // ----------------------------------------------------------------------
      //  OLD: 原始代码 (平滑滚动) - 已注释
      // ----------------------------------------------------------------------
      /*
      scrollTo({
          top: offset,
          behavior: "smooth"
      });
      */
    });
  });
}

export { setupSmoothAnchors };