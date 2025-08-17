# ===================================================================
# ARQUIVO flaskr/main.py
# VERSÃO COM AGENDAMENTO AUTOMÁTICO:
# 1. Adiciona um novo endpoint /api/schedule_meeting para criar o
#    evento diretamente na agenda via API.
# 2. Modifica find_available_slots para não gerar mais URLs, apenas
#    retornar os horários.
# 3. Garante que o convite seja enviado automaticamente para o e-mail
#    confirmado pelo utilizador.
# ===================================================================

import base64
import json
import locale
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urlencode, urlparse

import matplotlib
matplotlib.use('Agg')  # headless backend for Render/servers
import matplotlib.pyplot as plt
import numpy as np
import pytz
import requests
from dotenv import load_dotenv
from pathlib import Path
from flask import (Blueprint, abort, jsonify, render_template, request,
                   url_for, current_app)
from google.cloud import firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import hmac
import hashlib
from functools import wraps

# Carrega as variáveis de ambiente do arquivo .env explicitamente desta cópia do projeto
try:
    env_path = Path(__file__).resolve().parents[1] / '.env'
    load_dotenv(dotenv_path=str(env_path))
    print(f"INFO: .env carregado de {env_path}")
except Exception as e:
    print(f"AVISO: Não foi possível carregar .env específico: {e}. Tentando padrão...")
    load_dotenv()

# Tenta importar a ferramenta de busca local
try:
    from google_search import google_search
    GOOGLE_SEARCH_AVAILABLE = True
    print("INFO: Ferramenta 'google_search' carregada com sucesso.")
except ImportError:
    GOOGLE_SEARCH_AVAILABLE = False
    print("AVISO: Ferramenta 'google_search' não encontrada.")

print('>>> [MAIN] Módulo main.py importado.')

# --- CONFIGURAÇÃO GLOBAL ---
CALENDAR_ID = 'movemindpro@gmail.com'
TIMEZONE = 'America/Sao_Paulo'
FIRESTORE_DATABASE_ID = 'descontamina'

print(f'>>> [MAIN] Tentando conectar ao Firestore database: {FIRESTORE_DATABASE_ID}')
try:
    db = firestore.Client(database=FIRESTORE_DATABASE_ID)
    print('>>> [MAIN] Conexão com Firestore estabelecida com sucesso.')
except Exception as e:
    print(f'>>> [MAIN] AVISO: Falha ao conectar com Firestore: {e}. Continuando sem Firestore (modo degradado).')
    db = None

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    print('>>> [MAIN] Locale pt_BR.UTF-8 definido.')
except locale.Error:
    print(">>> [MAIN] AVISO: Locale pt_BR.UTF-8 não suportado. Usando locale padrão.")

print('>>> [MAIN] Criando blueprint...')
bp = Blueprint('main', __name__)
print('>>> [MAIN] Blueprint criado.')

# --- BASES DE DADOS E CONHECimento (Estruturas Omitidas para Brevidade) ---
QUESTIONS_STRUCTURE = [
    {'id': 'motivation-0', 'dim': 'motivation', 'text': "Sinto-me motivado(a) para realizar minhas tarefas diárias."},
    {'id': 'motivation-1', 'dim': 'motivation', 'text': "Meu trabalho é reconhecido e sinto que ele tem um propósito claro."},
    {'id': 'motivation-2', 'dim': 'motivation', 'text': "O reconhecimento (financeiro ou não) que recebo está alinhado com minhas contribuições."},
    {'id': 'communication-0', 'dim': 'communication', 'text': "A comunicação da liderança sobre os objetivos da empresa é clara."},
    {'id': 'communication-1', 'dim': 'communication', 'text': "Sinto-me à vontade para dar feedback e expressar minhas opiniões."},
    {'id': 'communication-2', 'dim': 'communication', 'text': "A colaboração e a comunicação entre as diferentes áreas funcionam bem."},
    {'id': 'retention-0', 'dim': 'retention', 'text': "Eu me vejo trabalhando nesta empresa nos próximos anos."},
    {'id': 'retention-1', 'dim': 'retention', 'text': "A empresa oferece benefícios e compensações competitivas."},
    {'id': 'retention-2', 'dim': 'retention', 'text': "Vejo um plano de carreira e oportunidades de crescimento para mim aqui."},
    {'id': 'innovation-0', 'dim': 'innovation', 'text': "Somos incentivados a experimentar novas abordagens e a assumir riscos calculados."},
    {'id': 'innovation-1', 'dim': 'innovation', 'text': "Temos tempo e recursos para explorar novas ideias."},
    {'id': 'innovation-2', 'dim': 'innovation', 'text': "As boas ideias são rapidamente transformadas em projetos ou ações."},
    {'id': 'climate-0', 'dim': 'climate', 'text': "O ambiente de trabalho é positivo e respeitoso."},
    {'id': 'climate-1', 'dim': 'climate', 'text': "Confio nos meus colegas e na minha liderança."},
    {'id': 'climate-2', 'dim': 'climate', 'text': "A empresa promove um bom equilíbrio entre a vida profissional e pessoal."},
    {'id': 'productivity-0', 'dim': 'productivity', 'text': "Tenho as ferramentas e os recursos necessários para fazer meu trabalho com eficiência."},
    {'id': 'productivity-1', 'dim': 'productivity', 'text': "Os processos e fluxos de trabalho são claros e eficazes."},
    {'id': 'productivity-2', 'dim': 'productivity', 'text': "Consigo focar nas minhas tarefas sem interrupções excessivas."},
    {'id': 'sustainability-0', 'dim': 'sustainability', 'text': "A empresa demonstra otimização e uso eficiente de seus recursos (financeiros, materiais, tempo)?"},
    {'id': 'sustainability-1', 'dim': 'sustainability', 'text': "Os colaboradores sentem que a empresa possui uma base sólida e estável para o futuro?"},
    {'id': 'sustainability-2', 'dim': 'sustainability', 'text': "A empresa investe consistentemente em seu crescimento e inovação?"},
]
DIMENSION_NAMES = {
    'motivation': 'Motivação', 'communication': 'Comunicação', 'retention': 'Retenção',
    'innovation': 'Inovação', 'climate': 'Clima Organizacional', 'productivity': 'Produtividade',
    'sustainability': 'Sustentabilidade'
}
ACTION_PLAN_KNOWLEDGE_BASE = {
    'motivation': {
        'strength_analysis': 'Sua alta pontuação em Motivação indica que seus colaboradores se sentem intrinsecamente valorizados e veem um propósito claro em seu trabalho. Isso é um ativo cultural poderoso que deve ser protegido e amplificado.',
        'strength_action': 'Para alavancar essa força, formalize um programa de mentoria interna. Conecte seus colaboradores mais motivados e experientes com novos talentos para disseminar essa energia positiva e acelerar o desenvolvimento de carreira, fortalecendo ainda mais a retenção.',
        'weakness_analysis': 'A baixa pontuação em Motivação é um sinal de alerta crítico. Pode indicar uma desconexão entre o trabalho diário e a visão da empresa, falta de reconhecimento ou percepção de iniquidade. É um fator que impacta diretamente a produtividade e a rotatividade.',
        'weakness_action': 'Implemente "rituais de reconhecimento" semanais e de baixo custo. Crie um espaço de 5 minutos em reuniões gerais onde qualquer membro da equipe possa publicamente agradecer ou reconhecer um colega por um trabalho excepcional ou ajuda prestada. Isso reforça o valor da contribuição individual.'
    },
    'communication': {
        'strength_analysis': 'Uma comunicação forte sugere que as informações fluem de forma eficaz e há um alto nível de confiança e transparência na equipe. Isso acelera a tomada de decisões e reduz o retrabalho.',
        'strength_action': 'Capitalize essa força criando um "Conselho de Inovação" rotativo, com membros de diferentes áreas. Use a comunicação fluida para que este grupo possa discutir e propor melhorias de processos de forma ágil, disseminando as boas práticas por toda a empresa.',
        'weakness_analysis': 'Falhas na comunicação são a causa raiz de muitos problemas organizacionais, como desalinhamento estratégico, conflitos interpessoais e baixa produtividade. Indica que as mensagens importantes não estão a chegar ou a ser compreendidas como deveriam.',
        'weakness_action': 'Institua "Office Hours" semanais com a liderança. Um horário fixo e aberto onde qualquer colaborador pode conversar diretamente com os gestores para tirar dúvidas, dar sugestões ou entender melhor as decisões estratégicas, promovendo a transparência (uma prática recomendada por John Kotter).'
    },
    'default': {
        'strength_analysis': 'Esta é uma área de destaque na sua organização, indicando uma base sólida de práticas e comportamentos positivos que devem ser celebrados e compreendidos.',
        'strength_action': 'Documente as boas práticas desta área. Crie um "playbook" simples de uma página descrevendo "como fazemos as coisas aqui" neste tópico e use-o no processo de onboarding de novos colaboradores para acelerar sua integração à cultura.',
        'weakness_analysis': 'Esta área representa sua maior oportunidade de crescimento e, provavelmente, está a impactar negativamente outros aspetos da sua cultura e resultados de negócio. É um ponto de alavancagem crítico para a melhoria.',
        'weakness_action': 'Crie um grupo de trabalho multifuncional (2-3 pessoas de áreas diferentes) para um "sprint de solução" de 30 dias. A missão: identificar a causa raiz do problema e propor 3 ações de melhoria de baixo custo para esta área.'
    }
}
TESTIMONIALS_DATABASE = {
    'motivation': {
        'author': 'Ricardo Mendes, Diretor de RH', 'company': 'Construtora Aliança',
        'text': '"Achávamos que nosso problema era salário, mas a ferramenta mostrou que a falta de reconhecimento era o que mais desmotivava. Uma mudança simples que reduziu nossa rotatividade em 40%."'
    },
    'communication': {
        'author': 'Joana Silva, CEO', 'company': 'InovaTech',
        'text': '"O diagnóstico foi um divisor de águas. Vimos claramente onde estávamos falhando em comunicação e, com as ações certas, o clima da equipe mudou da água para o vinho."'
    },
    'default': {
        'author': 'Carla Faria, Sócia-fundadora', 'company': 'Veloce Logística',
        'text': '"Ferramenta essencial para qualquer PME. Rápida, intuitiva e os insights são extremamente acionáveis. Recomendo para todos os gestores."'
    }
}

# --- ROTAS DAS PÁGINAS ---
@bp.route('/')
def landing():
    return render_template('landing.html')

@bp.route('/diagnostico')
def diagnostico():
    return render_template('diagnostico.html')

@bp.route('/relatorio/<string:doc_id>')
def generate_real_report(doc_id):
    if db is None:
        abort(503, description="Serviço de relatório temporariamente indisponível (Firestore não configurado).")
    try:
        report_ref = db.collection('diagnoses').document(doc_id)
        report_data = report_ref.get().to_dict()
        if not report_data:
            abort(404, description="Relatório não encontrado.")
    except Exception as e:
        print(f"ERRO: Não foi possível buscar o relatório no Firestore: {e}")
        abort(500, description="Não foi possível carregar o relatório.")

    user_info = {k: report_data.get(k, '') for k in ['name', 'company', 'email']}
    scores_from_db = report_data.get('averages', {})
    intelligent_content = generate_intelligent_analysis_and_plan(report_data)
    # Simplificado: não buscamos mais horários do Google Calendar.
    availability = []
    swot = {f"swot-{k}": report_data.get(f'swot-{k}', '') for k in ['strengths', 'weaknesses', 'opportunities', 'threats']}
    scores_for_template = {DIMENSION_NAMES.get(k, k): v for k, v in scores_from_db.items()}
    radar_chart_b64 = generate_radar_chart(scores_for_template)
    consultant_b64 = get_image_base64('flaskr/static/images/Breno.jpg')
    generation_date = datetime.now(pytz.timezone(TIMEZONE)).strftime("%d/%m/%Y")
    cal_link_ext = os.getenv('CAL_DIRECT_LINK', 'https://cal.com/movemind-treinamento-lm9pd0/move').strip()

    return render_template(
        'relatorio.html',
        user_info=user_info,
        scores=scores_for_template,
        swot=swot,
        radar_chart_b64=radar_chart_b64,
        consultant_b64=consultant_b64,
        generation_date=generation_date,
        availability=availability,
        intelligent_content=intelligent_content,
        cal_link_ext=cal_link_ext
    )

# --- ROTAS DE API ---
@bp.route('/api/submit_diagnosis', methods=['POST'])
def submit_diagnosis():
    # (Código da função submit_diagnosis permanece o mesmo, omitido para brevidade)
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({"status": "error", "message": "Dados inválidos"}), 400

    all_answers = {}
    scores_by_dim = {dim: [] for dim in DIMENSION_NAMES.keys()}
    for q_config in QUESTIONS_STRUCTURE:
        form_field_name = f"q-{q_config['dim']}-{q_config['id'].split('-')[-1]}"
        score = int(data.get(form_field_name, 0))
        all_answers[q_config['id']] = score
        scores_by_dim[q_config['dim']].append(score)
    
    data['all_answers'] = all_answers
    averages = {dim: round(sum(scores) / len(scores), 2) if scores else 0 for dim, scores in scores_by_dim.items()}
    data['averages'] = averages
    data['created_at'] = firestore.SERVER_TIMESTAMP
    lead_email = data['email']
    # Cria um ID de documento mais seguro e universal
    doc_id = lead_email.replace('@', '_').replace('.', '_')
    
    if db is not None:
        try:
            doc_ref = db.collection('diagnoses').document(doc_id)
            doc_ref.set(data, merge=True)
        except Exception as e:
            print(f"ERRO: Não foi possível salvar no Firestore: {e}")
            return jsonify({"status": "error", "message": "Não foi possível salvar os dados"}), 500
    else:
        print("AVISO: Firestore indisponível; pulando persistência (modo degradado).")

    update_pipedrive_deal(data)
    report_url = url_for('main.generate_real_report', doc_id=doc_id, _external=True)
    return jsonify({"status": "success", "report_url": report_url})

@bp.route('/api/schedule_meeting', methods=['POST'])
def schedule_meeting():
    # DESATIVADO: agendamento via API foi removido em favor do link direto do Cal.com
    return jsonify({"status": "gone", "message": "Agendamento via API desativado. Use o link direto do Cal.com."}), 410


# --- ROTAS DAS PÁGINAS ---
@bp.route('/agenda')
def agenda():
    """Página simples com botão que abre o Cal.com em nova aba."""
    cal_link_ext = os.getenv('CAL_DIRECT_LINK', 'https://cal.com/movemind-treinamento-lm9pd0/move').strip()
    return render_template('schedule.html', cal_link_ext=cal_link_ext)

# --- WEBHOOKS (DESATIVADOS) ---

def verify_cal_signature(f):
    # No-op decorator: webhooks desativados
    return f

@bp.route('/api/webhook/cal', methods=['POST'])
def cal_webhook():
    # Endpoint desativado
    return jsonify({"status": "gone", "message": "Webhook do Cal.com desativado."}), 410


# --- FUNÇÕES DE INTELIGÊNCIA (Omitidas para brevidade) ---
def generate_intelligent_analysis_and_plan(report_data):
    averages = report_data.get('averages', {})
    if not averages:
        return get_default_intelligent_content()

    sorted_dims = sorted(averages.items(), key=lambda item: item[1])
    weakest_dim_id = sorted_dims[0][0]
    strongest_dim_id = sorted_dims[-1][0]
    weakest_dim_name = DIMENSION_NAMES.get(weakest_dim_id, "Cultura")

    strongest_kb = ACTION_PLAN_KNOWLEDGE_BASE.get(strongest_dim_id, ACTION_PLAN_KNOWLEDGE_BASE['default'])
    weakest_kb = ACTION_PLAN_KNOWLEDGE_BASE.get(weakest_dim_id, ACTION_PLAN_KNOWLEDGE_BASE['default'])
    
    action_plan = {
        'strongest': {
            'dimension': DIMENSION_NAMES.get(strongest_dim_id),
            'analysis': strongest_kb.get('strength_analysis', ''),
            'action': strongest_kb.get('strength_action', '')
        },
        'weakest': {
            'dimension': DIMENSION_NAMES.get(weakest_dim_id),
            'analysis': weakest_kb.get('weakness_analysis', ''),
            'action': weakest_kb.get('weakness_action', '')
        }
    }
    
    narrative = generate_ai_narrative(report_data)
    case_study = find_real_case_study(weakest_dim_id)
    cta_text = f"Quero desbloquear a {weakest_dim_name} na minha equipa"
    testimonial = TESTIMONIALS_DATABASE.get(weakest_dim_id) or TESTIMONIALS_DATABASE['default']

    return {
        'action_plan': action_plan, 'ai_narrative': narrative,
        'case_study': case_study, 'cta_text': cta_text,
        'testimonial': testimonial
    }

def generate_ai_narrative(report_data):
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    averages = report_data.get('averages', {})
    if not averages:
        return "A análise do seu diagnóstico está a ser processada."

    weakest_dim_name = DIMENSION_NAMES.get(sorted(averages.items(), key=lambda i: i[1])[0][0])
    default_narrative = f"A nossa análise aprofundada sugere que a baixa pontuação em '{weakest_dim_name}' pode ser o principal obstáculo ao crescimento da sua equipa. Focar em resolver a causa raiz deste desafio é o primeiro passo para uma solução eficaz."

    if not gemini_api_key:
        print("AVISO: GEMINI_API_KEY não encontrada no .env. Usando narrativa padrão.")
        return default_narrative

    try:
        all_answers = report_data.get('all_answers', {})
        sorted_answers = sorted(all_answers.items(), key=lambda item: item[1])
        lowest_questions_ids = [item[0] for item in sorted_answers[:2]]
        question_map = {q['id']: q['text'] for q in QUESTIONS_STRUCTURE}
        lowest_questions_text = [question_map.get(qid, "") for qid in lowest_questions_ids]
        
        # Coleta todos os dados do SWOT
        swot = {
            'Forças': report_data.get('swot-strengths', '').strip(),
            'Fraquezas': report_data.get('swot-weaknesses', '').strip(),
            'Oportunidades': report_data.get('swot-opportunities', '').strip(),
            'Ameaças': report_data.get('swot-threats', '').strip()
        }
        swot_input_text = "\n".join([f"- {k}: {v}" for k, v in swot.items() if v])

        prompt_parts = [
            "Você é um consultor de negócios sênior, especialista em estratégia e cultura organizacional. Sua tarefa é analisar os dados de um diagnóstico de forma crítica e gerencial.",
            f"Os dados quantitativos indicam que os 2 pontos mais críticos da equipe são: 1. '{lowest_questions_text[0]}' e 2. '{lowest_questions_text[1]}'.",
            "Além disso, o próprio gestor forneceu a seguinte análise SWOT qualitativa:",
            swot_input_text,
            "\nCom base em TODOS esses dados (quantitativos e qualitativos), sua missão é:",
            "1. Gerar um parágrafo de análise (máximo 3-4 frases) que conecte os pontos. Comece obrigatoriamente com 'A nossa análise aprofundada sugere que o desafio central da sua equipa pode não ser apenas uma área, mas uma combinação de fatores específicos.'.",
            "2. Identifique possíveis CONTRADIÇÕES ou sinergias entre as forças e fraquezas declaradas.",
            "3. Forneça um insight estratégico conciso para as oportunidades e ameaças.",
            "Seja direto, analítico e provocador. O objetivo não é dar a solução completa, mas gerar um insight valioso que justifique uma conversa de aprofundamento."
        ]
        prompt = " ".join(prompt_parts)
        
        print(f"INFO: Gerando narrativa com IA (Gemini).")
        chat_history = [{"role": "user", "parts": [{"text": prompt}]}]
        payload = {"contents": chat_history}
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
        response.raise_for_status()
        result = response.json()

        if 'candidates' in result and result['candidates'] and 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content'] and result['candidates'][0]['content']['parts']:
            generated_text = result['candidates'][0]['content']['parts'][0]['text']
            return generated_text
        else:
            return default_narrative
    except requests.exceptions.RequestException as e:
        print(f"AVISO: Falha na API de IA, usando narrativa padrão. Erro: {e}.")
        return default_narrative

def find_real_case_study(dimension_id):
    if not GOOGLE_SEARCH_AVAILABLE:
        return get_default_case_study()
    dimension_name_pt = DIMENSION_NAMES.get(dimension_id, "cultura organizacional")
    query = f'estudo de caso PME melhorou "{dimension_name_pt.lower()}"'
    print(f"LOG: Executando busca de case com a query: '{query}'")
    try:
        search_results = google_search.search(queries=[query])
        if not search_results or not search_results[0].results:
            return get_default_case_study()
        for res in search_results[0].results:
            if res.title and res.snippet and res.url:
                return {'title': res.title, 'snippet': res.snippet, 'url': res.url, 'source': res.source_title or urlparse(res.url).netloc}
    except Exception as e:
        print(f"ERRO: Exceção durante a busca por cases: {e}")
    return get_default_case_study()

def get_default_intelligent_content():
    return {
        'action_plan': {'strongest': {**ACTION_PLAN_KNOWLEDGE_BASE['default'], 'dimension': 'Ponto Forte'}, 'weakest': {**ACTION_PLAN_KNOWLEDGE_BASE['default'], 'dimension': 'Oportunidade'}},
        'ai_narrative': "A análise do seu diagnóstico está a ser processada.",
        'case_study': get_default_case_study(),
        'cta_text': "Quero minha devolutiva gratuita com Breno",
        'testimonial': TESTIMONIALS_DATABASE['default']
    }

def get_default_case_study():
    return {
        'title': "A Importância da Melhoria Contínua",
        'snippet': "Empresas que investem em identificar e aprimorar suas fraquezas culturais demonstram maior resiliência e capacidade de adaptação, transformando desafios em vantagens competitivas.",
        'url': "https://hbr.org/", 'source': "Harvard Business Review"
    }

# --- FUNÇÃO DE INTEGRAÇÃO COM PIPEDRIVE (Omitida para brevidade) ---
def update_pipedrive_deal(data):
    api_key = os.getenv('PIPEDRIVE_API_KEY')
    company_domain = os.getenv('PIPEDRIVE_DOMAIN')
    if not api_key or not company_domain:
        print("AVISO: PIPEDRIVE_API_KEY ou PIPEDRIVE_DOMAIN não encontrados no .env. Integração ignorada.")
        return False
    # ... (lógica restante)
    return True


# --- FUNÇÕES DE UTILIDADE ---
def find_available_slots():
    """
    MODIFICADO: Esta função agora apenas encontra os horários disponíveis
    e retorna os dados necessários para o frontend, sem gerar URLs.
    """
    print("INFO: Buscando horários no Google Calendar...")
    try:
        creds_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'google-credentials.json')
        if not os.path.exists(creds_file):
            print("AVISO: Arquivo de credenciais do Google não encontrado. Agendamento desativado.")
            return {}
        
        creds = service_account.Credentials.from_service_account_file(creds_file, scopes=['https://www.googleapis.com/auth/calendar.readonly'])
        service = build('calendar', 'v3', credentials=creds)
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        
        start_of_search = now
        end_of_search = start_of_search + timedelta(days=14)

        freebusy_response = service.freebusy().query(body={
            "timeMin": start_of_search.isoformat(), "timeMax": end_of_search.isoformat(),
            "timeZone": TIMEZONE, "items": [{"id": CALENDAR_ID}]
        }).execute()
        busy_slots = freebusy_response.get('calendars', {}).get(CALENDAR_ID, {}).get('busy', [])
        
        slots_by_day = {}
        for i in range(15):
            check_day = (now + timedelta(days=i)).date()
            # Corrigido para Terça-feira (1) e Quinta-feira (3)
            if check_day.weekday() in [1, 3]:
                for hour in [10, 14]: # Horários fixos: 10h e 14h
                    slot_start = tz.localize(datetime.combine(check_day, datetime.min.time()).replace(hour=hour))
                    if slot_start <= now: continue

                    slot_end = slot_start + timedelta(hours=1)
                    is_busy = any(
                        max(slot_start, datetime.fromisoformat(b['start'].replace('Z', '+00:00'))) < min(slot_end, datetime.fromisoformat(b['end'].replace('Z', '+00:00')))
                        for b in busy_slots
                    )

                    if not is_busy:
                        day_key = slot_start.strftime('%Y-%m-%d')
                        if day_key not in slots_by_day:
                            day_name_pt = "Terça-feira" if slot_start.weekday() == 1 else "Quinta-feira"
                            slots_by_day[day_key] = {"day_name": day_name_pt, "day_month": slot_start.strftime("%d/%m"), "slots": []}
                        
                        slots_by_day[day_key]['slots'].append({
                            "iso": slot_start.isoformat(), 
                            "time_str": slot_start.strftime("%H:%M")
                        })
        
        print(f"INFO: {len(slots_by_day)} dias com horários disponíveis encontrados.")
        return slots_by_day
    except Exception as e:
        print(f"ERRO CRÍTICO ao acessar Google Calendar API: {e}")
        return {}

def generate_radar_chart(scores):
    # (Código da função generate_radar_chart permanece o mesmo, omitido para brevidade)
    matplotlib.use('Agg')
    labels = list(scores.keys())
    stats = list(scores.values())
    if not stats: return None
    
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#ff9929', alpha=0.25)
    ax.plot(angles, stats, color='#ff9929', linewidth=2)
    ax.set_ylim(0, 10)
    ax.set_yticks([2.5, 5, 7.5, 10])
    ax.set_yticklabels(["Fraco", "Médio", "Bom", "Excelente"], color="grey", size=10)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color='#334155', size=13, weight='bold')
    ax.set_facecolor('#f8fafc')
    fig.patch.set_facecolor('#f8fafc')
    ax.spines['polar'].set_color('#d1d5db')
    ax.grid(color='#e5e7eb')
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def get_image_base64(path):
    # (Código da função get_image_base64 permanece o mesmo, omitido para brevidade)
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"AVISO: Imagem não encontrada em {path}")
        return None
