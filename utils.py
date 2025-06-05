import os
from IPython.display import Image, display
from langchain_core.runnables.graph import MermaidDrawMethod
import nest_asyncio
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_chroma import Chroma

# 从Together AI导入嵌入模型
# 注意：可以调整此导入以使用不同的嵌入模型
from langchain_together import TogetherEmbeddings

# 使用阿里巴巴的GTE ModernBERT基础模型初始化嵌入模型
# 该模型用于将文本转换为向量表示，用于相似性搜索
EMBEDDING_MODEL = TogetherEmbeddings(
    model="Alibaba-NLP/gte-modernbert-base",
)

# 包含LangGraph文档的URL列表
# 这些URL涵盖了LangGraph框架的教程、概念和指南
LANGGRAPH_DOCS = [
    "https://langchain-ai.github.io/langgraph/",  # 主文档页面
    "https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/",  # 客户支持教程
    "https://langchain-ai.github.io/langgraph/tutorials/chatbots/information-gather-prompting/",  # 聊天机器人教程
    "https://langchain-ai.github.io/langgraph/tutorials/code_assistant/langgraph_code_assistant/",  # 代码助手教程
    "https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/",  # 多智能体协作
    "https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/",  # 智能体监督模式
    "https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/",  # 分层智能体团队
    "https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/",  # 计划和执行模式
    "https://langchain-ai.github.io/langgraph/tutorials/rewoo/rewoo/",  # ReWOO（无观察推理）教程
    "https://langchain-ai.github.io/langgraph/tutorials/llm-compiler/LLMCompiler/",  # LLM编译器教程
    "https://langchain-ai.github.io/langgraph/concepts/high_level/",  # 高级概念
    "https://langchain-ai.github.io/langgraph/concepts/low_level/",  # 低级概念
    "https://langchain-ai.github.io/langgraph/concepts/agentic_concepts/",  # 智能体概念
    "https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/",  # 人机交互循环概念
    "https://langchain-ai.github.io/langgraph/concepts/multi_agent/",  # 多智能体概念
    "https://langchain-ai.github.io/langgraph/concepts/persistence/",  # 持久化概念
    "https://langchain-ai.github.io/langgraph/concepts/streaming/",  # 流式处理概念
    "https://langchain-ai.github.io/langgraph/concepts/faq/"  # 常见问题
]

def get_langgraph_docs_retriever():
    """
    使用持久化的Chroma向量存储加载或创建LangGraph文档的检索器。
    
    该函数实现了缓存机制：
    1. 如果磁盘上已存在向量存储，则加载并返回它
    2. 如果不存在向量存储，则下载文档、创建嵌入、
       将其存储在向量存储中，并持久化到磁盘以供将来使用

    Returns:
        Retriever: 用于使用相似性搜索查询LangGraph文档的检索器对象
    """
    # 检查磁盘上是否已存在向量存储目录
    # 这允许我们跳过昂贵的文档加载和嵌入过程
    if os.path.exists("langgraph-docs-db"):
        print("从磁盘加载向量存储...")
        # 从持久化目录加载现有的向量存储
        vectorstore = Chroma(
            collection_name="langgraph-docs",  # 向量存储中集合的名称
            embedding_function=EMBEDDING_MODEL,  # 用于查询编码的嵌入模型
            persist_directory="langgraph-docs-db"  # 向量存储保存的目录
        )
        # 返回向量存储的检索器接口
        # lambda_mult=0 禁用MMR（最大边际相关性）多样性过滤器
        return vectorstore.as_retriever(lambda_mult=0)

    # 如果向量存储不存在，从头创建它
    print("从文档创建新的向量存储...")
    
    # 从LANGGRAPH_DOCS中的每个URL下载和加载文档
    # WebBaseLoader从网页获取内容并将其转换为Document对象
    docs = [WebBaseLoader(url).load() for url in LANGGRAPH_DOCS]
    
    # 将列表的列表展平为单个文档列表
    # 每个WebBaseLoader.load()返回一个列表，所以我们需要展平嵌套结构
    docs_list = [item for sublist in docs for item in sublist]
    
    # 将文档分割成更小的块以获得更好的检索性能
    # 较小的块允许更精确的相似性匹配
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=200,  # 每个块的最大令牌数（小块用于精确检索）
        chunk_overlap=0  # 块之间无重叠以避免冗余
    )
    doc_splits = text_splitter.split_documents(docs_list)
    
    # 使用指定配置创建新的Chroma向量存储
    vectorstore = Chroma(
        collection_name="langgraph-docs",  # 集合名称
        embedding_function=EMBEDDING_MODEL,  # 用于将文本转换为向量的嵌入模型
        persist_directory="langgraph-docs-db"  # 持久化向量存储的目录
    )
    
    # 将分割的文档添加到向量存储
    # 这为每个块创建嵌入并将其存储在向量数据库中
    vectorstore.add_documents(doc_splits)
    print("向量存储已创建并持久化到磁盘")
    
    # 返回新向量存储的检索器接口
    return vectorstore.as_retriever(lambda_mult=0)

def show_graph(graph, xray=False):
    """
    显示带有回退渲染的LangGraph mermaid图表。
    
    该函数尝试使用Mermaid将LangGraph渲染为可视化图表。
    它包含错误处理，如果默认渲染器失败，则回退到替代渲染器。
    
    Args:
        graph: 具有get_graph()方法用于可视化的LangGraph对象
        xray (bool): 是否在x射线模式下显示内部图表详细信息
        
    Returns:
        Image: 包含渲染图表的IPython Image对象
    """
    from IPython.display import Image
    
    try:
        # 首先尝试默认的mermaid渲染器（使用mermaid.ink服务）
        # 这是最快的选项，但可能由于网络问题或服务不可用而失败
        return Image(graph.get_graph(xray=xray).draw_mermaid_png())
    except Exception as e:
        # 如果默认渲染器失败，回退到pyppeteer
        # pyppeteer使用本地无头Chrome实例来渲染图表
        print(f"默认渲染器失败 ({e})，回退到pyppeteer...")
        
        # 应用nest_asyncio来处理Jupyter环境中的异步操作
        # 这是必要的，因为pyppeteer使用异步操作
        import nest_asyncio
        nest_asyncio.apply()
        
        # 导入MermaidDrawMethod枚举以指定绘制方法
        from langchain_core.runnables.graph import MermaidDrawMethod
        
        # 使用pyppeteer作为绘制方法（本地渲染）
        return Image(graph.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.PYPPETEER))