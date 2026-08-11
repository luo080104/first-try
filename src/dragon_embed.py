"""dragon_embed.py - 雕龙记忆层：中文小说章节嵌入 + Qdrant 语义检索（BGE-M3）
用法：
  python dragon_embed.py index <book_dir>    # 索引章节
  python dragon_embed.py search <book_dir> <query>  # 语义检索
"""
import glob
import os
import sys

QDRANT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dragon_qdrant')


def get_model():
    """BGE-M3 模型（首次需下载 ~2GB；可设 HF_ENDPOINT=https://hf-mirror.com 走国内镜像）"""
    try:
        from FlagEmbedding import BGEM3FlagModel
    except ImportError:
        print('未安装 FlagEmbedding（pip install FlagEmbedding）——模型依赖待装')
        raise
    return BGEM3FlagModel('BAAI/bge-m3', devices='cpu', pooling_method='cls')


def get_qdrant():
    from qdrant_client import QdrantClient
    return QdrantClient(path=QDRANT_PATH)


def index_book(model, book_dir: str):
    """把 定稿/正文/*.md 章节嵌入存入 Qdrant"""
    from qdrant_client.models import VectorParams, Distance, PointStruct
    chapters = sorted(glob.glob(os.path.join(book_dir, '定稿', '正文', '*.md')))
    if not chapters:
        print(f'未找到章节: {book_dir}/定稿/正文/')
        return
    client = get_qdrant()
    if not client.collection_exists('chapters'):
        client.create_collection('chapters', vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
    texts = []
    for ch in chapters:
        with open(ch, encoding='utf-8') as f:
            texts.append(f.read()[:4000])
    embs = model.encode_corpus(texts, return_dense=True)['dense_vecs']
    pts = [PointStruct(id=i, vector=embs[i].tolist(),
                       payload={'file': os.path.basename(chapters[i])})
           for i in range(len(texts))]
    client.upsert('chapters', pts)
    print(f'✅ 索引 {len(texts)} 章 → Qdrant（{QDRANT_PATH}）')


def search_book(model, book_dir: str, query: str, top: int = 5):
    client = get_qdrant()
    if not client.collection_exists('chapters'):
        print('未索引，先运行 index'); return
    q = model.encode_queries([query], return_dense=True)['dense_vecs'][0]
    try:
        hits = client.search('chapters', query_vector=q.tolist(), limit=top)
    except Exception as e:
        print(f'检索失败: {e}')
        return
    print(f'🔍 「{query}」最相关章节:')
    for h in hits:
        print(f'  {h.payload["file"]}  相似度={h.score:.3f}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, book = sys.argv[1], sys.argv[2]
    model = get_model()  # 首次下载 2GB（HF_ENDPOINT=https://hf-mirror.com 走镜像）
    if cmd == 'index':
        index_book(model, book)
    elif cmd == 'search' and len(sys.argv) >= 4:
        search_book(model, book, sys.argv[3])
