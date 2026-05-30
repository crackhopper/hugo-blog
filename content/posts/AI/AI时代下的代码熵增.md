---
title: AI时代下的代码熵增
date: 2026-04-02T10:02:22+08:00
tags: []
draft: false
---
![[AI时代下的代码熵增-intro-01.png]]

在人工智能代理（AI Agents）领域，软件工程的范式正在经历一场前所未有的剧变。这种变革最直观的体现，莫过于在实现相近核心功能的前提下，不同项目在代码规模上表现出的极端差异。OpenClaw（原名 Clawdbot/Moltbot）作为一个在短时间内迅速崛起的明星项目，其代码库规模已达到惊人的 43 万行至 80 万行不等 。与之形成鲜明对比的是，由香港大学（HKU）研究团队开发的 Nanobot 项目，仅通过约 4,000 行 Python 代码便实现了与之相当的代理核心功能 。这种“百倍差异”不仅引发了开发者社区对软件复杂性的反思，更揭示了在“氛围编程”（Vibe Coding）时代，开发效率、代码质量与系统架构之间复杂的互动关系。本文旨在从架构哲学、开发方法论、功能外延以及安全性等维度，深度解析 OpenClaw 代码冗余的成因及其与 Nanobot 的本质区别

（注意，本文大量采用 deep research 进行撰写，最后人工校验得到）
<!--more-->

# OpenClaw代码量
## 为什么OpenClaw有这么大的代码量？
OpenClaw 并非一个简单的 API 转发器，而是一个集成了大量原生组件的复杂生态系统。其代码 库不仅包含代理的逻辑，还包含了为不同操作系统定制的完整应用程序。分析显示，OpenClaw 的代码库中，约有 24% 的比例（超过 13.9 万行）属于原生移动端和桌面端的 UI 代码 $^9$ 。

|组件类别|估计代码行数|主要编程语言|功能描述|
|---|---|---|---|
|网关控制平面 (Gateway)|150,000+|TypeScript / Node.js|会话管理、渠道路由、事件总线|
|iOS 原生应用|78,000|Swift|为移动端提供原生通知、位置服务及 UI|
|Android 原生应用|10,000|Kotlin|移动端节点支持|
|macOS 桌面应用|50,000+|Swift|菜单栏集成及系统级快捷方式|
|浏览器自动化套件|80,000+|TypeScript|基于 Playwright 的 CDP 交互逻辑|
|视觉协作空间 (Canvas)|20,000+|React / Astro|提供 agent 驱动的实时视觉工作区|

可以看到，真正的核心代码 `Gateway` 所占比例极低。同时由于是AI生成的代码，会有大量的重复设计、corner case完善、硬编码一些查找表之类的。

## 真正的核心代码由人类完成，有多少代码？
Nanobot

|核心模块|代码行数 (约)|核心功能描述|
|---|---|---|
|`agent/loop.py`|800|代理的主推理循环，负责 LLM 输出与工具执行的衔接|
|`channels/`|1,200|模块化的通讯渠道适配器 (Telegram, Discord, Feishu 等)|
|`providers/`|500|统一的 LLM 供应商注册与调用接口|
|`memory/`|400|基于 Markdown 的状态化记忆管理系统|
|基础设施及 CLI|1,100|环境配置、安装向导及核心工具函数|

# “氛围编程”与 AI 生成的代码冗余
OpenClaw 的开发时间并不长，为何代码量却能如此巨大？这直接指向了 Peter Steinberger 所采用的开发模式——“氛围编程”（Vibe Coding）以及高强度的 AI 辅助生成 。

## 自动化生成带来的“软件废料”
OpenClaw 的主要开发者 Peter Steinberger 在短短 80 天内提交了超过 50 万行代码，平均每天产生约 6,475 行 。这种远超人类极限的产出率是通过同时运行 5 到 10 个 AI 编码代理来实现的，每个代理被分配不同的任务，开发者本人则充当架构师和代码审核员的角色 。

然而，这种高速度的代价是极低的代码密度和极高的冗余度。研究表明，AI 生成的代码往往具有以下特征，导致代码膨胀：
1. **缺乏重构的过度实现**：AI 在解决特定问题时，往往会生成一段完整的、自包含的代码片段，而不会考虑将其中的公共逻辑抽象为库。这种“以拷贝代替引用”的模式在短时间内迅速堆积了海量的逻辑重复 。
2. **防御性样板代码**：为了确保在复杂的单体架构（Monolith）中不崩溃，AI 会生成大量的防御性编程逻辑和冗余的错误处理，这些代码虽然增强了稳定性，但也使代码库变得臃肿且难以维护 。
3. **工程设计的非人化**：Steinberger 本人承认，他设计的代码库并非为了方便人类导航，而是为了让 AI 代理能够更高效地在其中工作 。这意味着代码中存在大量为了适应代理读取习惯而设计的结构，而非人类追求的简洁优雅。

批评者认为，如果由一个成熟的人类工程团队采用传统方式开发 OpenClaw，其核心功能可能只需要 6.9 万行代码，这意味着当前 43 万行代码中，约有 80% 至 90% 可能属于非必要的“代码废料”（Code Slop） 。

## 技能生态与注册表
OpenClaw 维护着一个名为 “ClawHub” 的庞大技能注册表，宣称拥有超过 1.3 万个社区技能 。为了管理这些技能的安装、版本控制、冲突检测以及安全审计，OpenClaw 开发了一整套类似于应用商店的基础设施。

# 安全性悖论：复杂性是安全的敌人
软件安全领域有一个公理：代码行数越多，潜在的漏洞（Attack Surface）就越多。

## 审计困境与供应链风险
OpenClaw 的 43 万行代码由 AI 在短时间内生成，这意味着没有任何一个人类审计员能够完整地理解其内部的所有逻辑流向。这种不可审计性带来了巨大的隐患 。

1. **权限过大（Root Access）**：OpenClaw 默认请求对宿主操作系统的完全控制权限，以便执行各种终端命令 。一旦 AI 代理发生幻觉，或者攻击者通过提示词注入（Prompt Injection）控制了代理，系统可能会发生灾难性的文件删除或敏感数据外泄 。
2. **供应链污染**：ClawHub 的 1.3 万个技能中，约有 20% 被安全研究人员标记为具有高风险权限或潜在的数据外传行为 。管理这种庞大且杂乱的技能生态，对 OpenClaw 现有的权限验证机制构成了严峻挑战 。

## 容器化与内核安全性

针对 OpenClaw 的这些缺陷，Nanobot 以及后续的衍生项目（如 NanoClaw 和 ZeroClaw）采取了截然不同的安全策略。

- **强制容器化（Mandatory Isolation）**：NanoClaw 仅通过 700 行 TypeScript 代码就实现了与 OpenClaw 核心功能对等的代理，但其最大的改进是强制要求每个代理运行在独立的 Docker 或 Apple 容器中，从操作系统层面实现了隔离 。

- **微内核架构**：Nanobot 采用类似于 Linux 内核的机制，核心只负责最基础的调度和通信，所有的敏感操作（如文件修改、网络访问）都需要显式的插件授权。这种 4,000 行的可审计代码库，使得安全团队可以在一天之内完成全面的安全审查 。

# 总结：如何在冗余与极简之间做出选择
OpenClaw 与 Nanobot 的对比，本质上是两种软件开发哲学的对决。

OpenClaw 的 43 万行代码是“氛围编程”时代的产物，它用空间的冗余换取了功能覆盖的速度。它适合那些追求“开箱即用”、希望 AI 能够深入渗透到电脑每一个角落、且拥有强大硬件支撑的进阶用户 。它是“全家桶式”的代理方案，虽然臃肿且存在安全隐患，但其生态的广度目前无人能及。

Nanobot 的 4,000 行代码则是“极简主义”的胜利，它将权力交还给开发者，提供了最高的可审计性和灵活性。它适合那些希望在资源受限环境运行代理、或者需要深入底层进行架构创新的研究者 。

正如行业分析所指出的，2026 年是“通用代理之年” 。在这个进程中，OpenClaw 提供了一个功能极其丰富的上限，而 Nanobot 则定义了一个极其稳固的下限。未来的主流架构，或许会在两者的碰撞中诞生——一个拥有 Nanobot 式极简内核，同时具备 OpenClaw 式广泛连接性的平衡点。无论如何，这百倍的代码规模差异，将作为 AI 影响软件工程史的一个里程碑，被长久地讨论和研究。

# 参考资料
1. OpenClaw vs Nanobot: Which AI Agent Framework Should You Use in 2026? |
DataCamp, 檢索日期：4月 2, 2026，
https://www.datacamp.com/blog/openclaw-vs-nanobot
2. Why does OpenClaw have 800,000+ lines of code?? Isn't it just a connector for
LL... | Hacker News, 檢索日期：4月 2, 2026，
https://news.ycombinator.com/item?id=47195074
3. HKUDS/nanobot: " nanobot: The Ultra-Lightweight OpenClaw" - GitHub, 檢索日期
：4月 2, 2026， https://github.com/HKUDS/nanobot
4. Unveiling the AI Revolution: What Does OpenClaw Do in 2026? - Skywork.ai, 檢索
日期：4月 2, 2026，
https://skywork.ai/skypage/en/ai-revolution-openclaw-2026/20364068898247516
16
5. OpenClaw vs Nanobot vs PicoClaw: A Brief Technical Comparison for AI Agent
Builders | by Somanath Balakrishnan | Feb, 2026 | Medium, 檢索日期：4月 2, 2026，
https://medium.com/@somanathtv/openclaw-vs-nanobot-vs-picoclaw-a-brief-te
chnical-comparison-for-ai-agent-builders-9d19089a414b
6. OpenClaw Joins OpenAI: The Real Story Behind the Viral Agent That Could
Change AI, 檢索日期：4月 2, 2026，
https://medium.com/@neonmaxima/openclaw-joins-openai-the-real-story-behin
d-the-viral-agent-that-could-change-ai-0f1c0282f31b
7. nanobot Roadmap: From Lightweight Agent to Agent Kernel ..., 檢索日期：4月 2,
2026， https://github.com/HKUDS/nanobot/discussions/431
8. What is NanoBot? Ultra-Lightweight AI Agent Framework | by Mehul Gupta -
Medium, 檢索日期：4月 2, 2026，
https://medium.com/data-science-in-your-pocket/what-is-nanobot-ultra-lightwe
ight-ai-agent-framework-c43ad6c40b11
9. nanobot: a 4,000-line Python alternative to openclaw that actually ..., 檢索日期：4
月 2, 2026，
https://www.reddit.com/r/ClaudeCode/comments/1qz34q5/nanobot_a_4000line_
python_alternative_to_openclaw/
10. The Ultimate Guide to OpenClaw: Architecture, Alternatives, and Deployment in
2026, 檢索日期：4月 2, 2026，
https://skywork.ai/skypage/en/ultimate-guide-openclaw-architecture-alternatives
-deployment/2038536816655339520
11. openclaw repositories - GitHub, 檢索日期：4月 2, 2026，
https://github.com/orgs/openclaw/repositories
12. openclaw/openclaw: Your own personal AI assistant. Any ... - GitHub, 檢索日期：4
月 2, 2026， https://github.com/openclaw/openclaw
13. OpenFang—The Game-Changing Open Source Agent Operating System That
Replaces OpenClaw | HackerNoon, 檢索日期：4月 2, 2026，
https://hackernoon.com/openfangthe-game-changing-open-source-agent-oper
ating-system-that-replaces-openclaw
14. Nanobot Tutorial: A Lightweight OpenClaw Alternative - DataCamp, 檢索日期：4月
2, 2026， https://www.datacamp.com/tutorial/nanobot-tutorial
15. The Ultimate Guide to OpenClaw GitHub Official Repository: Features,
Alternatives, and Setup - Skywork.ai, 檢索日期：4月 2, 2026，
https://skywork.ai/skypage/en/openclaw-github-repository-guide/2036751422357
868544
16. How does one person write 518,000 lines of code in 80 days? : r/openclaw -
Reddit, 檢索日期：4月 2, 2026，
https://www.reddit.com/r/openclaw/comments/1r2un9k/how_does_one_person_w
rite_518000_lines_of_code_in/
17. Transcript for OpenClaw: The Viral AI Agent that Broke the Internet - Peter
Steinberger | Lex Fridman Podcast #491, 檢索日期：4月 2, 2026，
https://lexfridman.com/peter-steinberger-transcript/
18. How one engineer uses AI coding agents to ship 118 commits/day across 6
parallel projects, 檢索日期：4月 2, 2026，
https://www.reddit.com/r/ChatGPTCoding/comments/1rfc26z/how_one_engineer
_uses_ai_coding_agents_to_ship/
19. The 12 Best OpenClaw Alternatives for 2026: Unifying AI with Team Productivity -
Lark, 檢索日期：4月 2, 2026，
https://www.larksuite.com/en_us/blog/openclaw-alternatives
20. OpenClaw creator visits Tokyo to pitch AI agents that organize your life - The
Japan Times, 檢索日期：4月 2, 2026，
https://www.japantimes.co.jp/business/2026/03/31/tech/openclaw-ai-agent-head
-interview/
21. OpenClaw Alternatives: NanoClaw, ZeroClaw, Moltis, and Every Competitor
Compared (2026) | AI Magicx Blog, 檢索日期：4月 2, 2026，
https://www.aimagicx.com/blog/openclaw-alternatives-comparison-2026
22. STOP USING OpenClaw: OpenClaw is getting worse.. These 2 Opensource
Alternatives are WAY BETTER!, 檢索日期：4月 2, 2026，
https://www.youtube.com/watch?v=ptXdlli33oc
23. How to Run OpenClaw with DigitalOcean, 檢索日期：4月 2, 2026，
https://www.digitalocean.com/community/tutorials/how-to-run-openclaw
24. How to run OpenClaw in Docker and Kubernetes - LumaDock VPS, 檢索日期：4月
2, 2026， https://lumadock.com/tutorials/openclaw-docker-kubernetes
25. Ultimate Guide to OpenClaw Official Documentation: Features, Alternatives &
Trends, 檢索日期：4月 2, 2026，
https://skywork.ai/skypage/en/openclaw-documentation-features-trends/203675
0159952056320
26. PicoClaw and Nanobot VS OpenClaw: The Rise of Ultra-Lightweight AI Assistants |
by Solana Levelup | Feb, 2026, 檢索日期：4月 2, 2026，
https://medium.com/@gemQueenx/picoclaw-and-nanobot-vs-openclaw-the-rise
-of-ultra-lightweight-ai-assistants-5077a4c611e8
27. Nanobot vs OpenClaw: A 4K-Line Agent Challenging a 430K-Line Giant - Reddit,
檢索日期：4月 2, 2026，
https://www.reddit.com/r/AISEOInsider/comments/1r6au4k/nanobot_vs_openclaw
_a_4kline_agent_challenging_a/
28. Anyone compared OpenClaw vs NanoClaw vs Nanobot? - Reddit, 檢索日期：4月
2, 2026，
https://www.reddit.com/r/openclaw/comments/1qwztvt/anyone_compared_open
claw_vs_nanoclaw_vs_nanobot/
29. Agent Wars 2026: OpenClaw vs. Memu vs. Nanobot vs…— Which Local AI Should
You Run? | by evoailabs, 檢索日期：4月 2, 2026，
https://evoailabs.medium.com/agent-wars-2026-openclaw-vs-memu-vs-nanobo
t-which-local-ai-should-you-run-8ef0869b2e0c
30. OpenClaw Alternatives for Enterprise Security: Honest 2026 Comparison -
Fountain City, 檢索日期：4月 2, 2026，
https://fountaincity.tech/resources/blog/openclaw-alternatives-enterprise-securit
y-comparison/
31. The Creator of OpenClaw Just Joined OpenAI. This Is Why That Matters. -
Techosaurus, 檢索日期：4月 2, 2026，
https://www.techosaurus.co.uk/news/2026/03/02/the-creator-of-openclaw-just/
32. From Clawdbot to OpenAI: What the OpenClaw Story Actually Tells Us | by
Cordero Core | Feb, 2026, 檢索日期：4月 2, 2026，
https://medium.com/@cdcore/from-clawdbot-to-openai-what-the-openclaw-sto
ry-actually-tells-us-79e3d034f227
33. OpenClaw's Founder Joined OpenAI. That Changes the Agent Story in 2026. -
Medium, 檢索日期：4月 2, 2026，
https://medium.com/@ryanshrott/openclaws-founder-joined-openai-that-chang
es-the-agent-story-in-2026-750dccead766