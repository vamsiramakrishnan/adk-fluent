//! Core types that map one-to-one to the Gemini Multimodal Live API wire format.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Model & Voice enumerations
// ---------------------------------------------------------------------------

/// Gemini models that support the Multimodal Live API.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum GeminiModel {
    #[serde(rename = "models/gemini-2.0-flash-live-001")]
    Gemini2_0FlashLive,
    #[serde(rename = "models/gemini-2.5-flash-preview-native-audio")]
    Gemini2_5FlashNativeAudio,
    /// Custom model string for forward compatibility.
    #[serde(untagged)]
    Custom(String),
}

impl Default for GeminiModel {
    fn default() -> Self {
        Self::Gemini2_0FlashLive
    }
}

impl std::fmt::Display for GeminiModel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Gemini2_0FlashLive => write!(f, "models/gemini-2.0-flash-live-001"),
            Self::Gemini2_5FlashNativeAudio => {
                write!(f, "models/gemini-2.5-flash-preview-native-audio")
            }
            Self::Custom(s) => write!(f, "{s}"),
        }
    }
}

/// Available voice presets for Gemini Live audio output.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Voice {
    Aoede,
    Charon,
    Fenrir,
    Kore,
    Puck,
    /// Custom voice name for forward compatibility.
    #[serde(untagged)]
    Custom(String),
}

impl Default for Voice {
    fn default() -> Self {
        Self::Puck
    }
}

// ---------------------------------------------------------------------------
// Audio format
// ---------------------------------------------------------------------------

/// Audio encoding formats supported by the Gemini Live API.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum AudioFormat {
    /// Raw 16-bit little-endian PCM.
    Pcm16,
    /// Opus-encoded audio.
    Opus,
}

impl Default for AudioFormat {
    fn default() -> Self {
        Self::Pcm16
    }
}

impl AudioFormat {
    /// MIME type string for this format.
    pub fn mime_type(&self) -> &'static str {
        match self {
            Self::Pcm16 => "audio/pcm",
            Self::Opus => "audio/opus",
        }
    }
}

/// Output modalities the model can produce.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Modality {
    Text,
    Audio,
    Image,
}

/// Voice activity detection sensitivity level.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Sensitivity {
    /// Disabled — no automatic detection.
    Disabled,
    /// Low sensitivity — fewer false positives, might miss soft speech.
    SensitivityLow,
    /// Medium sensitivity.
    SensitivityMedium,
    /// High sensitivity — catches everything, more false positives.
    SensitivityHigh,
    /// Automatic (server default).
    Automatic,
}

impl Default for Sensitivity {
    fn default() -> Self {
        Self::Automatic
    }
}

/// How the model should decide when to execute tool calls.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FunctionCallingMode {
    /// Model decides when to call functions.
    Auto,
    /// Model always calls one of the declared functions.
    Any,
    /// Model never calls functions.
    None,
}

impl Default for FunctionCallingMode {
    fn default() -> Self {
        Self::Auto
    }
}

/// Whether tool calls block model output or run concurrently.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FunctionCallingBehavior {
    /// Model waits for tool response before continuing.
    Blocking,
    /// Model continues generating while tool executes.
    NonBlocking,
}

impl Default for FunctionCallingBehavior {
    fn default() -> Self {
        Self::Blocking
    }
}

// ---------------------------------------------------------------------------
// Content primitives
// ---------------------------------------------------------------------------

/// A blob of inline data (audio, image, etc.) sent to or received from Gemini.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Blob {
    pub mime_type: String,
    pub data: String, // base64-encoded
}

/// A function call request from the model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FunctionCall {
    pub name: String,
    pub args: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
}

/// A function call response sent back to the model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FunctionResponse {
    pub name: String,
    pub response: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
}

/// Executable code returned by the model.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutableCode {
    pub language: String,
    pub code: String,
}

/// Result of code execution.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CodeExecutionResult {
    pub outcome: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
}

/// A single part of a `Content` message.
/// Parts are polymorphic — discriminated by field presence, not a type tag.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Part {
    Text {
        text: String,
    },
    InlineData {
        #[serde(rename = "inlineData")]
        inline_data: Blob,
    },
    FunctionCall {
        #[serde(rename = "functionCall")]
        function_call: FunctionCall,
    },
    FunctionResponse {
        #[serde(rename = "functionResponse")]
        function_response: FunctionResponse,
    },
    ExecutableCode {
        #[serde(rename = "executableCode")]
        executable_code: ExecutableCode,
    },
    CodeExecutionResult {
        #[serde(rename = "codeExecutionResult")]
        code_execution_result: CodeExecutionResult,
    },
}

/// A content message containing a role and a sequence of parts.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Content {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    pub parts: Vec<Part>,
}

// ---------------------------------------------------------------------------
// Tool declarations
// ---------------------------------------------------------------------------

/// Schema for a single function that the model can call.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FunctionDeclaration {
    pub name: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parameters: Option<serde_json::Value>,
}

/// A collection of function declarations to send during setup.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolDeclaration {
    pub function_declarations: Vec<FunctionDeclaration>,
}

/// Controls how and when the model uses tools.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub function_calling_config: Option<FunctionCallingConfig>,
}

impl ToolConfig {
    /// Auto mode — model decides when to call functions.
    pub fn auto() -> Self {
        Self {
            function_calling_config: Some(FunctionCallingConfig {
                mode: FunctionCallingMode::Auto,
                behavior: None,
            }),
        }
    }
}

/// Configuration for function calling behavior.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FunctionCallingConfig {
    pub mode: FunctionCallingMode,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub behavior: Option<FunctionCallingBehavior>,
}

// ---------------------------------------------------------------------------
// Session configuration (builder pattern)
// ---------------------------------------------------------------------------

/// Speech configuration for audio output.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SpeechConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voice_config: Option<VoiceConfig>,
}

/// Voice configuration within speech config.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VoiceConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prebuilt_voice_config: Option<PrebuiltVoiceConfig>,
}

/// Prebuilt voice selection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PrebuiltVoiceConfig {
    pub voice_name: String,
}

/// Input audio transcription configuration.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InputAudioTranscription {}

/// Output audio transcription configuration.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OutputAudioTranscription {}

/// Server-side VAD configuration for the setup message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RealtimeInputConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub automatic_activity_detection: Option<AutomaticActivityDetection>,
}

/// Automatic activity detection (VAD) settings.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AutomaticActivityDetection {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub disabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_of_speech_sensitivity: Option<Sensitivity>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub end_of_speech_sensitivity: Option<Sensitivity>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prefix_padding_ms: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub silence_duration_ms: Option<u32>,
}

/// Session resumption configuration.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionResumptionConfig {
    /// Opaque handle from a previous session for transparent resume.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub handle: Option<String>,
}

/// Generation config sent in the setup message.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerationConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_modalities: Option<Vec<Modality>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speech_config: Option<SpeechConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_output_tokens: Option<u32>,
}

/// Complete session configuration — the builder entrypoint.
#[derive(Debug, Clone)]
pub struct SessionConfig {
    pub api_key: String,
    pub model: GeminiModel,
    pub generation_config: GenerationConfig,
    pub system_instruction: Option<Content>,
    pub tools: Vec<ToolDeclaration>,
    pub tool_config: Option<ToolConfig>,
    pub input_audio_transcription: Option<InputAudioTranscription>,
    pub output_audio_transcription: Option<OutputAudioTranscription>,
    pub realtime_input_config: Option<RealtimeInputConfig>,
    pub session_resumption: Option<SessionResumptionConfig>,
    pub input_audio_format: AudioFormat,
    pub output_audio_format: AudioFormat,
    pub input_sample_rate: u32,
    pub output_sample_rate: u32,
}

impl SessionConfig {
    /// Create a new session configuration with the given API key.
    pub fn new(api_key: impl Into<String>) -> Self {
        Self {
            api_key: api_key.into(),
            model: GeminiModel::default(),
            generation_config: GenerationConfig {
                response_modalities: Some(vec![Modality::Audio]),
                speech_config: None,
                temperature: None,
                top_p: None,
                top_k: None,
                max_output_tokens: None,
            },
            system_instruction: None,
            tools: Vec::new(),
            tool_config: None,
            input_audio_transcription: None,
            output_audio_transcription: None,
            realtime_input_config: None,
            session_resumption: None,
            input_audio_format: AudioFormat::Pcm16,
            output_audio_format: AudioFormat::Pcm16,
            input_sample_rate: 16000,
            output_sample_rate: 24000,
        }
    }

    /// Set the Gemini model.
    pub fn model(mut self, model: GeminiModel) -> Self {
        self.model = model;
        self
    }

    /// Set the output voice.
    pub fn voice(mut self, voice: Voice) -> Self {
        let voice_name = match &voice {
            Voice::Aoede => "Aoede".to_string(),
            Voice::Charon => "Charon".to_string(),
            Voice::Fenrir => "Fenrir".to_string(),
            Voice::Kore => "Kore".to_string(),
            Voice::Puck => "Puck".to_string(),
            Voice::Custom(name) => name.clone(),
        };
        self.generation_config.speech_config = Some(SpeechConfig {
            voice_config: Some(VoiceConfig {
                prebuilt_voice_config: Some(PrebuiltVoiceConfig { voice_name }),
            }),
        });
        self
    }

    /// Set the system instruction.
    pub fn system_instruction(mut self, instruction: impl Into<String>) -> Self {
        self.system_instruction = Some(Content {
            role: None,
            parts: vec![Part::Text {
                text: instruction.into(),
            }],
        });
        self
    }

    /// Set response modalities.
    pub fn response_modalities(mut self, modalities: Vec<Modality>) -> Self {
        self.generation_config.response_modalities = Some(modalities);
        self
    }

    /// Configure for text-only mode (no audio output).
    pub fn text_only(mut self) -> Self {
        self.generation_config.response_modalities = Some(vec![Modality::Text]);
        self.generation_config.speech_config = None;
        self
    }

    /// Add a tool declaration.
    pub fn add_tool(mut self, tool: ToolDeclaration) -> Self {
        self.tools.push(tool);
        self
    }

    /// Set tool configuration.
    pub fn tool_config(mut self, config: ToolConfig) -> Self {
        self.tool_config = Some(config);
        self
    }

    /// Enable input audio transcription.
    pub fn enable_input_transcription(mut self) -> Self {
        self.input_audio_transcription = Some(InputAudioTranscription {});
        self
    }

    /// Enable output audio transcription.
    pub fn enable_output_transcription(mut self) -> Self {
        self.output_audio_transcription = Some(OutputAudioTranscription {});
        self
    }

    /// Set the temperature for generation.
    pub fn temperature(mut self, temp: f32) -> Self {
        self.generation_config.temperature = Some(temp);
        self
    }

    /// Configure server-side VAD.
    pub fn server_vad(mut self, detection: AutomaticActivityDetection) -> Self {
        self.realtime_input_config = Some(RealtimeInputConfig {
            automatic_activity_detection: Some(detection),
        });
        self
    }

    /// Enable session resumption.
    pub fn session_resumption(mut self, handle: Option<String>) -> Self {
        self.session_resumption = Some(SessionResumptionConfig { handle });
        self
    }

    /// Set input audio format and sample rate.
    pub fn input_audio(mut self, format: AudioFormat, sample_rate: u32) -> Self {
        self.input_audio_format = format;
        self.input_sample_rate = sample_rate;
        self
    }

    /// Set output audio format and sample rate.
    pub fn output_audio(mut self, format: AudioFormat, sample_rate: u32) -> Self {
        self.output_audio_format = format;
        self.output_sample_rate = sample_rate;
        self
    }

    /// Build the WebSocket URL for connecting to the Gemini Live API.
    pub fn ws_url(&self) -> String {
        format!(
            "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={}",
            self.api_key
        )
    }

    /// Build the model URI used in the setup message.
    pub fn model_uri(&self) -> String {
        self.model.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn session_config_builder() {
        let config = SessionConfig::new("test-key")
            .model(GeminiModel::Gemini2_0FlashLive)
            .voice(Voice::Kore)
            .system_instruction("Be helpful.")
            .temperature(0.7);

        assert_eq!(config.api_key, "test-key");
        assert_eq!(config.model, GeminiModel::Gemini2_0FlashLive);
        assert!(config.system_instruction.is_some());
        assert_eq!(config.generation_config.temperature, Some(0.7));
    }

    #[test]
    fn text_only_mode() {
        let config = SessionConfig::new("key").text_only();
        assert_eq!(
            config.generation_config.response_modalities,
            Some(vec![Modality::Text])
        );
        assert!(config.generation_config.speech_config.is_none());
    }

    #[test]
    fn model_serialization() {
        let model = GeminiModel::Gemini2_0FlashLive;
        let json = serde_json::to_string(&model).unwrap();
        assert_eq!(json, "\"models/gemini-2.0-flash-live-001\"");
    }

    #[test]
    fn voice_serialization() {
        let voice = Voice::Kore;
        let json = serde_json::to_string(&voice).unwrap();
        assert_eq!(json, "\"Kore\"");
    }

    #[test]
    fn part_text_round_trip() {
        let part = Part::Text {
            text: "Hello".to_string(),
        };
        let json = serde_json::to_string(&part).unwrap();
        let parsed: Part = serde_json::from_str(&json).unwrap();
        assert_eq!(part, parsed);
    }

    #[test]
    fn part_inline_data_round_trip() {
        let part = Part::InlineData {
            inline_data: Blob {
                mime_type: "audio/pcm".to_string(),
                data: "AQID".to_string(),
            },
        };
        let json = serde_json::to_string(&part).unwrap();
        assert!(json.contains("inlineData"));
        let parsed: Part = serde_json::from_str(&json).unwrap();
        assert_eq!(part, parsed);
    }

    #[test]
    fn part_function_call_round_trip() {
        let part = Part::FunctionCall {
            function_call: FunctionCall {
                name: "get_weather".to_string(),
                args: serde_json::json!({"city": "London"}),
                id: Some("call-1".to_string()),
            },
        };
        let json = serde_json::to_string(&part).unwrap();
        assert!(json.contains("functionCall"));
        let parsed: Part = serde_json::from_str(&json).unwrap();
        assert_eq!(part, parsed);
    }

    #[test]
    fn ws_url_contains_key() {
        let config = SessionConfig::new("my-secret-key");
        let url = config.ws_url();
        assert!(url.starts_with("wss://"));
        assert!(url.contains("key=my-secret-key"));
    }
}
