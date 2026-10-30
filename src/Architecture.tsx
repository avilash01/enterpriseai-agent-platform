import { Activity, ArrowDown, ArrowRight, AudioLines, Bot, Boxes, Braces, ClipboardList, Database, FileText, GitBranch, LockKeyhole, Radio, Scale, Search, Server, ShieldCheck, Workflow, Zap } from 'lucide-react';

const stages=[
  {title:'React console',sub:'React · TypeScript',icon:Boxes,tone:'violet'},
  {title:'FastAPI',sub:'JWT · RBAC · audit',icon:Server,tone:'cyan'},
  {title:'LangGraph',sub:'Shared state · eight nodes',icon:GitBranch,tone:'violet'},
  {title:'Approval gate',sub:'Human-approved actions',icon:LockKeyhole,tone:'amber'},
];
const modules=[
  {name:'Intake planner',desc:'Defines scope and a bounded execution plan',icon:ClipboardList,tone:'violet'},
  {name:'Research analyst',desc:'Separates supplied evidence from unknowns',icon:Search,tone:'cyan'},
  {name:'Knowledge retriever',desc:'Hybrid vector, graph, and lexical retrieval',icon:Database,tone:'amber'},
  {name:'Analysis agent',desc:'Reasons over evidence and flags inference',icon:Activity,tone:'green'},
  {name:'Writing agent',desc:'Drafts a grounded response with citations',icon:FileText,tone:'violet'},
  {name:'Quality reviewer',desc:'Checks grounding, coverage, and clarity',icon:ShieldCheck,tone:'cyan'},
  {name:'Decision agent',desc:'Recommends the next action for review',icon:Scale,tone:'amber'},
  {name:'Automation planner',desc:'Prepares an approved workflow event',icon:Workflow,tone:'green'},
];
const services=[
  {title:'Qdrant + Neo4j',text:'Vector retrieval · entity links · graph expansion',tag:'Knowledge',icon:Database,tone:'cyan'},
  {title:'PostgreSQL + Redis',text:'Users, runs, documents · retrieval cache',tag:'State',icon:Database,tone:'violet'},
  {title:'RabbitMQ',text:'Durable queue for approved automation events',tag:'Events',icon:Radio,tone:'amber'},
  {title:'Ollama + Whisper',text:'Local LLM, vision, embeddings, audio/video',tag:'Multimodal',icon:AudioLines,tone:'green'},
  {title:'Zapier',text:'Catch Hook receives reviewed, approved workflow events',tag:'Automation',icon:Zap,tone:'amber'},
  {title:'Prometheus + Grafana',text:'API metrics and operational dashboards',tag:'Telemetry',icon:Activity,tone:'violet'},
];
export default function Architecture(){return <div className="arch-page">
  <div className="arch-intro"><div><div className="arch-kicker"><Radio size={13}/> CLOUD-INDEPENDENT · DOCKER COMPOSE</div><h2>Enterprise agent architecture</h2><p>Eight LangGraph agents share state across a defined workflow. Knowledge, data, automation, and observability services are wired into the Compose stack.</p></div><div className="arch-badge"><Boxes size={14}/> Compose architecture</div></div>
  <section className="arch-panel"><div className="arch-panel-head"><div><h3>Request and approval path</h3><p>Authenticated request → agent graph → grounded response → explicitly approved automation event.</p></div><span className="arch-status"><i/> LANGGRAPH · EIGHT NODES</span></div>
    <div className="arch-flow">{stages.map((s,i)=><div className="arch-flow-wrap" key={s.title}><div className={`arch-node ${s.tone}`}><div className="arch-node-icon"><s.icon size={17}/></div><div className="arch-node-copy"><b>{s.title}</b><small>{s.sub}</small></div><em>In code</em></div>{i<stages.length-1&&<div className="arch-arrow"><ArrowRight size={15}/></div>}</div>)}</div>
    <div className="agent-layer"><div className="layer-label"><span>LANGGRAPH SPECIALIST AGENTS</span><small>Shared invocation state · sequential graph edges · cited context</small></div><div className="agent-grid">{modules.map((m,i)=><div className={`specialist ${m.tone}`} key={m.name}><div className="specialist-index">0{i+1}</div><div className="specialist-icon"><m.icon size={16}/></div><b>{m.name}</b><p>{m.desc}</p><span>LangGraph node</span></div>)}</div></div>
  </section>
  <section className="arch-panel"><div className="arch-panel-head"><div><h3>Integrated service plane</h3><p>These services are included in Docker Compose and connected to the API or event worker.</p></div><Boxes size={17}/></div><div className="service-grid">{services.map(s=><div className="service-tile" key={s.title}><div className={`service-icon ${s.tone}`}><s.icon size={16}/></div><div className="service-copy"><b>{s.title}</b><small>{s.text}</small></div><span className="service-tag">{s.tag}</span></div>)}</div></section>
  <section className="arch-bottom-grid">
    <div className="arch-panel"><div className="arch-panel-head"><div><h3>Multimodal knowledge pipeline</h3><p>Ingestion creates vector chunks and linked graph entities.</p></div><FileText size={17}/></div><div className="service-list"><Service icon={FileText} title="Documents" text="PDF · DOCX · text · CSV · JSON" tag="Parse + chunk" tone="cyan"/><Service icon={Search} title="Hybrid retrieval" text="Qdrant similarity + lexical rerank + Neo4j expansion" tag="Cited evidence" tone="violet"/><Service icon={AudioLines} title="Images · audio · video" text="Ollama vision · local Whisper · sampled video frames" tag="Local models" tone="amber"/></div></div>
    <div className="arch-panel"><div className="arch-panel-head"><div><h3>Zapier execution path</h3><p>Events are queued durably before they reach your Zap.</p></div><Workflow size={17}/></div><div className="zap-flow"><div className="zap-step"><span className="zap-logo">EA</span><div><b>EnterpriseAI API</b><small>RBAC checks · explicit human approval</small></div></div><div className="zap-line"><ArrowDown size={15}/></div><div className="zap-step"><span className="zap-logo">RMQ</span><div><b>RabbitMQ</b><small>Durable workflow event queue</small></div></div><div className="zap-line"><ArrowDown size={15}/></div><div className="zap-step"><span className="zap-logo zapier"><Zap size={15}/></span><div><b>Zapier Catch Hook</b><small>Routes into your configured Zap actions</small></div></div><div className="privacy-note"><LockKeyhole size={13}/> The Catch Hook URL stays in the worker environment. Only approved event payloads are forwarded.</div></div></div>
  </section>
  <div className="arch-footer"><span><Bot size={14}/> Orchestration: LangGraph</span><span><Database size={14}/> Data plane: local containers</span><span><ShieldCheck size={14}/> Security: JWT · RBAC · audit</span><span><Braces size={14}/> Metrics: Prometheus</span></div>
</div>}
function Service({icon:Icon,title,text,tag,tone}:{icon:typeof FileText,title:string,text:string,tag:string,tone:string}){return <div className="service-row"><div className={`service-icon ${tone}`}><Icon size={15}/></div><div className="service-copy"><b>{title}</b><small>{text}</small></div><span className="service-tag">{tag}</span></div>}
