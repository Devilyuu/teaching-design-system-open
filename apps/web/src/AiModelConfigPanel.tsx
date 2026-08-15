import { CheckCircle2, PlugZap, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { enableAiModelConfig, getAiModelConfig, testAiModelConfig, updateAiModelConfig } from "./api";
import type { AiModelConfig } from "./types";


const emptyConfig: AiModelConfig = {
  id: null,
  base_url: "",
  model_name: "",
  api_key_status: "未配置",
  enabled: false,
  connection_status: "unconfigured",
  last_tested_at: null,
  updated_at: null
};


export default function AiModelConfigPanel() {
  const [config, setConfig] = useState<AiModelConfig>(emptyConfig);
  const [draft, setDraft] = useState({ base_url: "", model_name: "", api_key: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getAiModelConfig()
      .then((value) => {
        setConfig(value);
        setDraft({ base_url: value.base_url, model_name: value.model_name, api_key: "" });
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function run(action: () => Promise<AiModelConfig>, successMessage: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const value = await action();
      setConfig(value);
      setMessage(successMessage);
      setDraft((current) => ({ ...current, base_url: value.base_url, model_name: value.model_name, api_key: "" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(() => updateAiModelConfig(draft), "配置已保存，请测试连接");
  }

  const connectionLabel = config.connection_status === "connected"
    ? "连接正常"
    : config.connection_status === "failed" ? "连接失败" : "尚未测试";

  return (
    <section className="panel ai-model-panel">
      <div className="panel-head">
        <div><h3>AI 模型配置</h3><span className="sub">OpenAI 兼容接口，仅管理员可维护</span></div>
        <div className="status-line">
          <span className={`tag ${config.connection_status === "connected" ? "green" : ""}`}>{connectionLabel}</span>
          <span className={`tag ${config.enabled ? "green" : ""}`}>{config.enabled ? "已启用" : "未启用"}</span>
        </div>
      </div>
      <div className="panel-body">
        <form className="form-grid" onSubmit={save}>
          <label>接口地址<input required type="url" value={draft.base_url} placeholder="https://example.com/v1" onChange={(event) => setDraft({ ...draft, base_url: event.target.value })} /></label>
          <label>模型名称<input required value={draft.model_name} placeholder="model-name" onChange={(event) => setDraft({ ...draft, model_name: event.target.value })} /></label>
          <label>API 密钥<input type="password" value={draft.api_key} placeholder={config.api_key_status === "已配置" ? "留空则保持原密钥" : "请输入 API 密钥"} onChange={(event) => setDraft({ ...draft, api_key: event.target.value })} /></label>
          <div className="field-block"><span>密钥状态</span><strong>{config.api_key_status}</strong><small>密钥只加密保存在服务器，不会返回浏览器。</small></div>
          <div className="form-actions ai-model-actions">
            <button className="btn primary" type="submit" disabled={busy}><Save className="icon" />保存配置</button>
            <button className="btn" type="button" disabled={busy || !config.id} onClick={() => void run(testAiModelConfig, "连接测试通过")}><PlugZap className="icon" />测试连接</button>
            <button className="btn" type="button" disabled={busy || config.connection_status !== "connected"} onClick={() => void run(() => enableAiModelConfig(!config.enabled), config.enabled ? "AI 生成已停用" : "AI 生成已启用")}><CheckCircle2 className="icon" />{config.enabled ? "停用" : "启用"}</button>
          </div>
        </form>
        <p className="plain-note">生成时仅发送当前课次所需的课程依据。请确认所配置服务允许处理学校教学资料。</p>
        {message && <div className="notice">{message}</div>}
        {error && <div className="error">{error}</div>}
      </div>
    </section>
  );
}
