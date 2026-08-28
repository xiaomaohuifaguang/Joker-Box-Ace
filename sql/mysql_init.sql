-- Joker Box Ace 远程库初始化 SQL（MySQL）
-- 本文件由 gen_init_sql.py 从模型自动生成，请勿手改
-- 建议库的字符集: utf8mb4 / utf8mb4_unicode_ci

CREATE TABLE IF NOT EXISTS cat_ace_api_keys (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(64) NOT NULL COMMENT '名称，标识这个 key 给谁用', 
	description VARCHAR(255) COMMENT '详细描述', 
	key_value VARCHAR(64) NOT NULL COMMENT 'key 明文（界面回显用）', 
	key_hash VARCHAR(64) NOT NULL COMMENT 'sha256(key)，校验索引；唯一约束自带索引', 
	enabled BOOL NOT NULL, 
	expires_at DATETIME COMMENT '留空 = 永不过期', 
	last_used_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (key_hash)
);
