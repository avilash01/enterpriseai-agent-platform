import { Activity, ArrowDown, ArrowRight, Bot, Boxes, Braces, CheckCircle2, ClipboardList, Database, FileText, GitBranch, LockKeyhole, Radio, Scale, Search, Server, ShieldCheck, Workflow, Zap } from 'lucide-react';

const stages=[
  {title:'Web console',sub:'React · TypeScript',icon:Boxes,state:'Live in MVP',tone:'violet'},
  {title:'API gateway',sub:'FastAPI · request validation',icon:Server,state:'Live in MVP',tone:'cyan'},
  {title:'ADK orchestrator',sub:'Deterministic agent workflow',icon:GitBranch,state:'Live in MVP',tone:'violet'},
  {title:'Approval gate',sub:'Opt-in Zapier event only',icon:LockKeyhole,state:'Live in MVP',tone:'amber'},
];
const modules=[
  {name:'Intake planner',desc:'Bounds the request and sets a plan',icon:ClipboardList,tone:'violet',state:'Agent'},
  {name:'Research analyst',desc:'Extracts supplied context; no invented sources',icon:Search,tone:'cyan',state:'Agent'},
  {name:'Knowledge retriever',desc:'Reports source coverage honestly',icon:Database,tone:'amber',state:'Agent'},
  {name:'Analysis agent',desc:'Separates supplied facts and inference',icon:Activity,tone:'green',state:'Agent'},
  {name:'Writing agent',desc:'Drafts from shared workflow state',icon:FileText,tone:'violet',state:'Agent'},
  {name:'Quality reviewer',desc:'Checks grounding before final response',icon:ShieldCheck,tone:'cyan',state:'Agent'},
  {name:'Decision agent',desc:'Recommends a next step for human review',icon:Scale,tone:'amber',state:'Agent'},
  {name:'Automation planner',desc:'Prepares an optional Zapier follow-up',icon:Workflow,tone:'green',state:'Agent'},
];
export default function Architecture(){return <div className="arch-page">
  <div className="arch-intro"><div><div className="arch-kicker"><Radio size={13}/> CLOUD-INDEPENDENT · CONTAINER-FIRST</div><h2>Enterprise agent architecture</h2><p>Google ADK orchestrates the request. Model and automation credentials stay server-side. The current build runs locally with Docker Compose.</p></div><div className="arch-badge"><CheckCircle2 size={14}/> MVP architecture</div></div>
  <section className="arch-panel"><div className="arch-panel-head"><div><h3>Request path</h3><p>One request flows through the agent workflow, then returns a reviewed response.</p></div><span className="arch-status"><i/> ADK SEQUENTIAL WORKFLOW</span></div>
    <div className="arch-flow">{stages.map((s,i)=><div className="arch-flow-wrap" key={s.title}><div className={`arch-node ${s.tone}`}><div className="arch-node-icon"><s.icon size={17}/></div><div className="arch-node-copy"><b>{s.title}</b><small>{s.sub}</small></div><em>{s.state}</em></div>{i<stages.length-1&&<div className="arch-arrow"><ArrowRight size={15}/></div>}</div>)}</div>
    <div className="agent-layer"><div className="layer-label"><span>ADK SPECIALIST AGENTS</span><small>Shared invocation state · explicit output keys</small></div><div className="agent-grid">{modules.map((m,i)=><div className={`specialist ${m.tone}`} key={m.name}><div className="specialist-index">0{i+1}</div><div className="specialist-icon"><m.icon size={16}/></div><b>{m.name}</b><p>{m.desc}</p><span>{m.state}</span></div>)}</div></div>
  </section>
  <section className="arch-bottom-grid">
    <div className="arch-panel"><div className="arch-panel-head"><div><h3>Knowledge & model services</h3><p>Model adapters run locally or through an optional provider.</p></div><Database size={17}/></div><div className="service-list"><Service icon={Database} title="Knowledge pipeline" text="Document parsing → chunking → metadata" tag="Planned" tone="cyan"/><Service icon={Search} title="Hybrid retrieval" text="Qdrant vectors + Neo4j entity graph + reranking" tag="Planned" tone="violet"/><Service icon={Database} title="Session & durable memory" text="ADK in-memory session today · Redis/PostgreSQL target" tag="In memory" tone="amber"/><Service icon={Zap} title="Model execution" text="Ollama locally · Groq via LiteLLM adapter" tag="Configured" tone="green"/></div></div>
    <div className="arch-panel"><div className="arch-panel-head"><div><h3>Zapier automation bridge</h3><p>Run metadata can enter a user-owned Zap after explicit approval.</p></div><Workflow size={17}/></div><div className="zap-flow"><div className="zap-step"><span className="zap-logo">EA</span><div><b>EnterpriseAI</b><small>run.completed event</small></div></div><div className="zap-line"><ArrowDown size={15}/></div><div className="zap-step"><span className="zap-logo zapier"><Zap size={15}/></span><div><b>Webhooks by Zapier</b><small>Catch Hook · URL stored on API</small></div></div><div className="zap-line"><ArrowDown size={15}/></div><div className="zap-step"><span className="zap-logo apps"><Braces size={15}/></span><div><b>Your Zap actions</b><small>Slack · email · CRM · other apps</small></div></div><div className="privacy-note"><LockKeyhole size={13}/> Sends run ID, agent names, and timestamp only. No prompt or answer.</div></div></div>
  </section>
  <div className="arch-footer"><span><Bot size={14}/> Orchestration: Google ADK</span><span><Database size={14}/> Data plane: local containers</span><span><LockKeyhole size={14}/> Secrets: backend environment</span></div>
</div>}
function Service({icon:Icon,title,text,tag,tone}:{icon:typeof Database,title:string,text:string,tag:string,tone:string}){return <div className="service-row"><div className={`service-icon ${tone}`}><Icon size={15}/></div><div className="service-copy"><b>{title}</b><small>{text}</small></div><span className={`service-tag ${tag==='Planned'?'planned':''}`}>{tag}</span></div>}
