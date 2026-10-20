//! Official pinned LiteRT CPU C ABI. No Python, GPU, ONNX or graph modifications.
use libloading::Library;
use std::{ffi::c_void, path::Path, sync::Arc};
type Pointer = *mut c_void;
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
struct Api {
    _library: Library,
    model: unsafe extern "C" fn(*const c_void, usize) -> Pointer,
    model_delete: unsafe extern "C" fn(Pointer),
    options: unsafe extern "C" fn() -> Pointer,
    threads: unsafe extern "C" fn(Pointer, i32),
    options_delete: unsafe extern "C" fn(Pointer),
    interpreter: unsafe extern "C" fn(Pointer, Pointer) -> Pointer,
    interpreter_delete: unsafe extern "C" fn(Pointer),
    resize: unsafe extern "C" fn(Pointer, i32, *const i32, i32) -> i32,
    allocate: unsafe extern "C" fn(Pointer) -> i32,
    input: unsafe extern "C" fn(Pointer, i32) -> Pointer,
    output: unsafe extern "C" fn(Pointer, i32) -> Pointer,
    bytes: unsafe extern "C" fn(Pointer) -> usize,
    tensor_type: unsafe extern "C" fn(Pointer) -> i32,
    copy_in: unsafe extern "C" fn(Pointer, *const c_void, usize) -> i32,
    invoke: unsafe extern "C" fn(Pointer) -> i32,
    copy_out: unsafe extern "C" fn(Pointer, *mut c_void, usize) -> i32,
}
impl Api {
    fn open(root: &Path) -> Result<Arc<Self>> {
        crate::artifacts::verify(root)?;
        let library: Library = unsafe {
            libloading::os::windows::Library::load_with_flags(
                root.join("libLiteRt.dll"),
                0x100 | 0x1000,
            )?
            .into()
        };
        macro_rules! symbol {
            ($name:literal) => {
                unsafe { *library.get(concat!($name, "\0").as_bytes())? }
            };
        }
        Ok(Arc::new(Self {
            model: symbol!("TfLiteModelCreate"),
            model_delete: symbol!("TfLiteModelDelete"),
            options: symbol!("TfLiteInterpreterOptionsCreate"),
            threads: symbol!("TfLiteInterpreterOptionsSetNumThreads"),
            options_delete: symbol!("TfLiteInterpreterOptionsDelete"),
            interpreter: symbol!("TfLiteInterpreterCreate"),
            interpreter_delete: symbol!("TfLiteInterpreterDelete"),
            resize: symbol!("TfLiteInterpreterResizeInputTensor"),
            allocate: symbol!("TfLiteInterpreterAllocateTensors"),
            input: symbol!("TfLiteInterpreterGetInputTensor"),
            output: symbol!("TfLiteInterpreterGetOutputTensor"),
            bytes: symbol!("TfLiteTensorByteSize"),
            tensor_type: symbol!("TfLiteTensorType"),
            copy_in: symbol!("TfLiteTensorCopyFromBuffer"),
            invoke: symbol!("TfLiteInterpreterInvoke"),
            copy_out: symbol!("TfLiteTensorCopyToBuffer"),
            _library: library,
        }))
    }
}
pub struct Model {
    api: Arc<Api>,
    _data: Vec<u8>,
    model: Pointer,
    interpreter: Pointer,
}
impl Model {
    fn open(api: Arc<Api>, root: &Path, name: &str, shape: &[i32]) -> Result<Self> {
        let data = std::fs::read(root.join(name))?;
        let model = unsafe { (api.model)(data.as_ptr().cast(), data.len()) };
        if model.is_null() {
            return Err("Cannot load keyword graph".into());
        }
        let mut result = Self {
            api,
            _data: data,
            model,
            interpreter: std::ptr::null_mut(),
        };
        unsafe {
            let options = (result.api.options)();
            if options.is_null() {
                return Err("Cannot allocate CPU inference options".into());
            }
            (result.api.threads)(options, 1);
            result.interpreter = (result.api.interpreter)(model, options);
            (result.api.options_delete)(options);
            if result.interpreter.is_null()
                || (result.api.resize)(result.interpreter, 0, shape.as_ptr(), shape.len() as i32)
                    != 0
                || (result.api.allocate)(result.interpreter) != 0
            {
                return Err("Cannot initialize keyword CPU graph".into());
            }
        }
        Ok(result)
    }
    fn run(&mut self, input: &[f32], count: usize) -> Result<Vec<f32>> {
        if input.len() > 4096 || count > 4096 {
            return Err("Oversized keyword tensor".into());
        }
        unsafe {
            let tensor = (self.api.input)(self.interpreter, 0);
            if tensor.is_null()
                || (self.api.tensor_type)(tensor) != 1
                || (self.api.bytes)(tensor) != std::mem::size_of_val(input)
                || (self.api.copy_in)(tensor, input.as_ptr().cast(), std::mem::size_of_val(input))
                    != 0
                || (self.api.invoke)(self.interpreter) != 0
            {
                return Err("Keyword CPU inference failed".into());
            }
            let tensor = (self.api.output)(self.interpreter, 0);
            let mut result = vec![0.0f32; count];
            if tensor.is_null()
                || (self.api.tensor_type)(tensor) != 1
                || (self.api.bytes)(tensor) != count * 4
                || (self.api.copy_out)(tensor, result.as_mut_ptr().cast(), count * 4) != 0
                || result.iter().any(|value| !value.is_finite())
            {
                return Err("Invalid keyword CPU output".into());
            }
            Ok(result)
        }
    }
}
impl Drop for Model {
    fn drop(&mut self) {
        unsafe {
            if !self.interpreter.is_null() {
                (self.api.interpreter_delete)(self.interpreter);
            }
            (self.api.model_delete)(self.model);
        }
    }
}
pub struct Neural {
    mel: Model,
    embedding: Model,
    keyword: Model,
    pcm: std::collections::VecDeque<i16>,
    pending: std::collections::VecDeque<i16>,
    mels: std::collections::VecDeque<f32>,
    features: std::collections::VecDeque<f32>,
    pub score: f32,
}
impl Neural {
    pub fn open(root: &Path) -> Result<Self> {
        let api = Api::open(root)?;
        let mut result = Self {
            mel: Model::open(api.clone(), root, "melspectrogram.tflite", &[1, 1760])?,
            embedding: Model::open(api.clone(), root, "embedding_model.tflite", &[1, 76, 32, 1])?,
            keyword: Model::open(api, root, "hey_jarvis_v0.1.tflite", &[1, 16, 96])?,
            pcm: Default::default(),
            pending: Default::default(),
            mels: Default::default(),
            features: Default::default(),
            score: 0.0,
        };
        result.reset()?;
        Ok(result)
    }
    pub fn reset(&mut self) -> Result<()> {
        self.pcm = vec![0; 480].into();
        self.pending.clear();
        self.mels = vec![1.0; 76 * 32].into();
        self.features = self
            .embedding
            .run(&vec![1.0; 76 * 32], 96)?
            .repeat(16)
            .into();
        self.score = 0.0;
        Ok(())
    }
    pub fn feed(&mut self, samples: &[i16]) -> Result<bool> {
        if samples.len() > 16000 {
            return Err("Oversized keyword audio frame".into());
        }
        self.pending.extend(samples);
        let mut detected = false;
        self.score = 0.0;
        while self.pending.len() >= 1280 {
            self.pcm.extend(self.pending.drain(..1280));
            let raw: Vec<f32> = self.pcm.iter().map(|value| *value as f32).collect();
            self.mels.extend(
                self.mel
                    .run(&raw, 8 * 32)?
                    .iter()
                    .map(|value| value / 10.0 + 2.0),
            );
            self.mels.drain(..self.mels.len() - 76 * 32);
            self.features
                .extend(self.embedding.run(self.mels.make_contiguous(), 96)?);
            self.features.drain(..self.features.len() - 16 * 96);
            self.score = self
                .score
                .max(self.keyword.run(self.features.make_contiguous(), 1)?[0]);
            detected |= self.score >= 0.5;
            self.pcm.drain(..1280);
        }
        Ok(detected)
    }
}
