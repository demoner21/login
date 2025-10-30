-- Habilita as extensões necessárias para o banco de dados.
-- PostGIS é usado para tipos e funções espaciais.
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;
-- uuid-ossp é usado para gerar UUIDs.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;

-- Define um tipo ENUM para o status dos jobs.
CREATE TYPE public.job_status AS ENUM (
    'PENDING',
    'PROCESSING',
    'COMPLETED',
    'FAILED'
);

-- Função para atualizar o campo 'updated_at' automaticamente.
CREATE OR REPLACE FUNCTION public.trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Tabela de usuários do sistema.
CREATE TABLE public.usuario (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    data_criacao TIMESTAMPTZ DEFAULT NOW(),
    data_modificacao TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela para armazenar os refresh tokens dos usuários.
CREATE TABLE public.user_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, token_hash)
);

-- Tabela para armazenar as Regiões de Interesse (ROI).
-- Utiliza a extensão PostGIS para dados geométricos.
CREATE TABLE public.regiao_de_interesse (
    roi_id SERIAL PRIMARY KEY,
    user_id INTEGER,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,
    geometria public.geometry(Geometry, 4326),
    tipo_origem VARCHAR(50),
    status VARCHAR(20) DEFAULT 'ativo',
    metadata JSONB,
    sistema_referencia VARCHAR(50) DEFAULT 'EPSG:4326',
    nome_arquivo_original VARCHAR(255),
    arquivos_relacionados JSONB,
    data_criacao TIMESTAMPTZ DEFAULT NOW(),
    data_modificacao TIMESTAMPTZ DEFAULT NOW(),
    roi_pai_id INTEGER,
    tipo_roi VARCHAR(20),
    nome_propriedade VARCHAR(255),
    nome_talhao VARCHAR(255),
    variedade VARCHAR(255),
    CONSTRAINT chk_tipo_roi CHECK (tipo_roi IS NULL OR tipo_roi IN ('PROPRIEDADE', 'TALHAO'))
);

-- Tabela de jobs de análise associados a uma ROI.
CREATE TABLE public.analysis_jobs (
    job_id SERIAL PRIMARY KEY,
    roi_id INTEGER,
    user_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    parent_job_id INTEGER
);

-- Tabela para armazenar os resultados das análises.
CREATE TABLE public.analysis_results (
    result_id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL,
    date_analyzed DATE NOT NULL,
    predicted_atr REAL NOT NULL,
    UNIQUE (job_id, date_analyzed)
);

-- Tabela genérica de jobs do sistema.
CREATE TABLE public.jobs (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL,
    status public.job_status DEFAULT 'PENDING' NOT NULL,
    message TEXT,
    result_path VARCHAR(1024),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Relações para 'user_refresh_tokens'
ALTER TABLE public.user_refresh_tokens
    ADD CONSTRAINT fk_user_refresh_tokens_user_id FOREIGN KEY (user_id) REFERENCES public.usuario(id) ON DELETE CASCADE;

-- Relações para 'regiao_de_interesse'
ALTER TABLE public.regiao_de_interesse
    ADD CONSTRAINT fk_regiao_de_interesse_user_id FOREIGN KEY (user_id) REFERENCES public.usuario(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_regiao_de_interesse_roi_pai_id FOREIGN KEY (roi_pai_id) REFERENCES public.regiao_de_interesse(roi_id) ON DELETE SET NULL;

-- Relações para 'analysis_jobs'
ALTER TABLE public.analysis_jobs
    ADD CONSTRAINT fk_analysis_jobs_user_id FOREIGN KEY (user_id) REFERENCES public.usuario(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_analysis_jobs_roi_id FOREIGN KEY (roi_id) REFERENCES public.regiao_de_interesse(roi_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_analysis_jobs_parent_job_id FOREIGN KEY (parent_job_id) REFERENCES public.analysis_jobs(job_id) ON DELETE SET NULL;

-- Relações para 'analysis_results'
ALTER TABLE public.analysis_results
    ADD CONSTRAINT fk_analysis_results_job_id FOREIGN KEY (job_id) REFERENCES public.analysis_jobs(job_id) ON DELETE CASCADE;

-- Relações para 'jobs'
ALTER TABLE public.jobs
    ADD CONSTRAINT fk_jobs_user_id FOREIGN KEY (user_id) REFERENCES public.usuario(id) ON DELETE CASCADE;

-- Criação de índices para otimização de consultas
CREATE INDEX idx_user_refresh_tokens_user_id ON public.user_refresh_tokens(user_id);
CREATE INDEX idx_regiao_interesse_geometria ON public.regiao_de_interesse USING GIST (geometria);
CREATE INDEX idx_roi_user_id ON public.regiao_de_interesse(user_id);
CREATE INDEX idx_roi_roi_pai_id ON public.regiao_de_interesse(roi_pai_id);
CREATE INDEX idx_roi_tipo_roi ON public.regiao_de_interesse(tipo_roi);
CREATE INDEX idx_roi_nome_propriedade ON public.regiao_de_interesse(nome_propriedade);
CREATE INDEX idx_analysis_jobs_user_id ON public.analysis_jobs(user_id);
CREATE INDEX idx_analysis_jobs_roi_id ON public.analysis_jobs(roi_id);

-- Trigger para atualizar 'updated_at' na tabela 'jobs'
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON public.jobs
FOR EACH ROW
EXECUTE FUNCTION public.trigger_set_timestamp();

-- Tabela para registrar os diferentes modelos de análise de ATR
CREATE TABLE public.modelos_atr (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,
    mes_referencia DATE NOT NULL, -- Armazena 'YYYY-MM-01', representa o mês de validade do modelo
    caminho_modelo_joblib VARCHAR(1024) NOT NULL, -- Caminho para o .joblib do modelo
    caminho_estatisticas_joblib VARCHAR(1024) NOT NULL, -- Caminho para feature_statistics.joblib [cite: 4]
    caminho_features_joblib VARCHAR(1024) NOT NULL, -- Caminho para features_list.joblib [cite: 4]
    ativo BOOLEAN DEFAULT true,
    data_criacao TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(mes_referencia) -- Garante que haja apenas um modelo ativo por mês
);

-- Comentário sobre a tabela de modelos
COMMENT ON COLUMN public.modelos_atr.mes_referencia IS 'Mês de referência para o qual o modelo foi treinado (armazena sempre o dia 01 do mês).';

-- Tabela para a programação de colheita dos talhões
CREATE TABLE public.programacao_colheita (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    talhao_id INTEGER NOT NULL,
    data_prevista_colheita DATE NOT NULL,
    modelo_id_sugerido INTEGER, -- O modelo que o sistema sugere para essa data
    analysis_job_id INTEGER, -- Link para o job de análise quando for executado
    status VARCHAR(20) DEFAULT 'PENDENTE' NOT NULL, -- Ex: PENDENTE, ANALISADO, COLHIDO
    data_criacao TIMESTAMPTZ DEFAULT NOW(),
    data_modificacao TIMESTAMPTZ DEFAULT NOW(),

    -- Relações (Foreign Keys)
    CONSTRAINT fk_programacao_user_id FOREIGN KEY (user_id) 
        REFERENCES public.usuario(id) ON DELETE CASCADE,
    CONSTRAINT fk_programacao_talhao_id FOREIGN KEY (talhao_id) 
        REFERENCES public.regiao_de_interesse(roi_id) ON DELETE CASCADE,
    CONSTRAINT fk_programacao_modelo_id FOREIGN KEY (modelo_id_sugerido) 
        REFERENCES public.modelos_atr(id) ON DELETE SET NULL,
    CONSTRAINT fk_programacao_analysis_job FOREIGN KEY (analysis_job_id) 
        REFERENCES public.analysis_jobs(job_id) ON DELETE SET NULL,

    -- Garante que um talhão não possa ser agendado duas vezes para o mesmo dia
    UNIQUE(user_id, talhao_id, data_prevista_colheita)
);

-- Índices para otimizar consultas na nova tabela
CREATE INDEX idx_programacao_user_id ON public.programacao_colheita(user_id);
CREATE INDEX idx_programacao_talhao_id ON public.programacao_colheita(talhao_id);
CREATE INDEX idx_programacao_data_colheita ON public.programacao_colheita(data_prevista_colheita);

-- Trigger para atualizar 'updated_at' (reutilizando a função existente)
CREATE TRIGGER set_timestamp_programacao
BEFORE UPDATE ON public.programacao_colheita
FOR EACH ROW
EXECUTE FUNCTION public.trigger_set_timestamp();

ALTER TABLE public.modelos_atr DROP CONSTRAINT IF EXISTS modelos_atr_mes_referencia_key;

-- 2. Adiciona a coluna 'variedade' que faltava
-- Esta coluna deve corresponder ao nome da variedade no metadado do talhão
ALTER TABLE public.modelos_atr ADD COLUMN variedade VARCHAR(100) NOT NULL;

-- 3. Adiciona uma nova restrição UNIQUE composta
-- Isso garante que você só pode ter um modelo por variedade por mês
ALTER TABLE public.modelos_atr ADD CONSTRAINT unq_modelo_variedade_mes UNIQUE (variedade, mes_referencia);

-- 4. Cria um índice para buscas rápidas por variedade
CREATE INDEX idx_modelos_atr_variedade ON public.modelos_atr(variedade);