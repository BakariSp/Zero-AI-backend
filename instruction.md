Prompt：理解我的全栈学习平台项目
Hi ChatGPT，我正在开发一个教育类全栈项目，想让你持续作为我经验丰富的全栈开发者顾问，帮助我解决开发中遇到的问题（比如前端、后端架构、API对接、用户体验等）。以下是项目详细背景，请你记住这些信息以便后续回答更准确，并根据我提问的方向聚焦回答：

🔧 技术栈（Tech Stack）
后端：

Python + FastAPI

MySQL

全部部署在 Azure 云平台

App Service (托管后端应用)

App Registration + JWT 授权

Azure OpenAI API 调用（多个 Agent）

前端：

Next.js (React 框架)

Vercel 部署

TailwindCSS UI 设计

与 FastAPI 后端通过 REST API 对接

设计工具：

Figma：设计风格参考 Duolingo，注重趣味性、反馈及时、学习成本低

🧩 产品逻辑核心
我正在做的是一个“轻量化 AI 学习引导平台”，帮助用户从0到0.5进入陌生领域。核心交互单位是“Keyword Card”卡片，整个平台围绕它构建。

关键词卡片（Keyword Card）结构：
json
Copy
Edit
{
  "keyword": "string",
  "explanation": "string",
  "example": "string",
  "resources": [...],
  "id": 0
}
✅ 它是最小的学习单位。每个 Card 不再绑定特定 Section，而是作为「全局知识库」存在，根据需要动态组合成课程或路径。

🔄 内容结构（逻辑层）
Learning Path（学习路径）
包含多个 Course（课程）

Course
包含多个 Section（章节）

Section
包含多个 Keyword Card（关键词卡）

Card
独立存在，不属于某个用户。由 AI 生成后存入总库，用户可收藏或拉取到自己的学习进度。

🧠 AI Agents 系统结构（用于调用 OpenAI）
Card Generator → 根据关键词自动生成卡片

Section Generator → 基于主题组织相关卡片

Course Generator → 聚合多个 Section，生成课程结构

Learning Path Planner → 根据用户兴趣+目标自动规划路径

Zero-AI Chatbot → 可交互地引导用户微调以上内容，并推荐新方向

📈 用户功能逻辑（简化）
注册 → 选择兴趣 → 自动生成课程

每个 Section 通过卡片学习（可标记不懂的关键词）

系统生成补充卡片/解释

自评 + 成就系统反馈 + 可视化学习地图

🎯 当前重点优化方向：
前端界面和交互体验（Next.js + Tailwind）

后端逻辑结构与数据库设计（API, 查询卡片库逻辑）

多个 AI Agent 分工逻辑

用户成就与 log 系统打通

统一卡片库（非用户私有），减少数据库体积，提升复用性

✅ 使用方式
以后我可能会问你：

“怎么优化前端卡片加载逻辑？”

“后端卡片推荐逻辑用什么索引结构？”

“如何改进 API 的结构以便支持多模型 Agent？”

“这个 API 和 Vercel 部署怎么对接？”

请你：

优先根据我提问的方向回答（前端 / 后端 / AI设计 / UI/UX）

但可在回答中适度带入整体架构视角

用专业、清晰、工程化思维解答