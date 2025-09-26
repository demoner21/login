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
