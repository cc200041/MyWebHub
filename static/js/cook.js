const { createApp, reactive, toRefs, computed } = Vue;

const app = createApp({
    setup() {
        const state = reactive({
            // 左侧 AI 厨师聊天
            chatInput: "",
            chatLog: [
                {
                    role: "ai",
                    text: "告诉我你现在厨房/冰箱里有哪些食材，我帮你规划今天可以做什么菜～",
                },
            ],
            isThinking: false,

            // 右侧推荐 + 搜索
            suggestList: [],   // AI 推荐列表
            searchQ: "",       // 手动搜索关键词
            searchList: [],    // 手动搜索结果

            // 当前菜谱详情
            curDish: null,
            recipeChatInput: "",
            recipeChatLog: [],
        });

        const showList = computed(() => {
            // 有搜索词时优先展示搜索结果，否则展示 AI 推荐列表
            return state.searchQ ? state.searchList : state.suggestList;
        });

        const appendChat = (role, text) => {
            state.chatLog.push({ role, text });
        };

        const sendChat = async () => {
            const msg = state.chatInput.trim();
            if (!msg || state.isThinking) return;

            appendChat("user", msg);
            state.chatInput = "";
            state.isThinking = true;

            try {
                const res = await axios.post("/api/cook/chef_chat", { message: msg });
                const data = res.data || {};
                appendChat("ai", data.reply || "好啦，菜单已经更新在右边啦～");

                // 更新推荐列表
                state.suggestList = (data.recipes || []).map((r) => ({
                    name: r.name,
                    score: r.score || 0,
                    missing: r.missing || [],
                    exists: !!r.exists,
                    category: r.category || "",
                }));
            } catch (e) {
                appendChat("ai", "网络有点问题，我刚刚没听清，再说一遍？");
            } finally {
                state.isThinking = false;
            }
        };

        const doSearch = async () => {
            const q = state.searchQ.trim();
            if (!q) {
                state.searchList = [];
                return;
            }
            try {
                const res = await axios.get(`/api/cook/search?q=${encodeURIComponent(q)}`);
                state.searchList = res.data || [];
            } catch (e) {
                console.error(e);
            }
        };

        const loadDish = async (name) => {
            try {
                const res = await axios.get(`/api/cook/detail?name=${encodeURIComponent(name)}`);
                const d = res.data;
                // 修正相对图片路径
                let html = (d.html || "").replace(
                    /src="\.\//g,
                    `src="/data/HowToCook/dishes/${d.category}/`
                );
                state.curDish = {
                    name: d.name,
                    category: d.category,
                    calories: d.calories,
                    html,
                    tags: d.tags || [],
                };
                // 每次切换菜谱时，清空右下角小聊天
                state.recipeChatLog = [];
                state.recipeChatInput = "";
            } catch (e) {
                alert("加载菜谱失败");
            }
        };

        const genToken = async () => {
            if (!state.curDish) return;
            try {
                const res = await axios.post("/api/cook/token", {
                    name: state.curDish.name,
                    cal: state.curDish.calories || 0,
                });
                const token = res.data.token;
                window.prompt("请复制口令，并在 FitLife 中导入：", token);
            } catch (e) {
                alert("生成口令失败");
            }
        };

        const askRecipe = async () => {
            const q = state.recipeChatInput.trim();
            if (!q || !state.curDish) return;
            state.recipeChatLog.push({ role: "user", text: q });
            state.recipeChatInput = "";
            try {
                const res = await axios.post("/api/cook/ask_chef", {
                    recipe: state.curDish.name,
                    question: q,
                });
                state.recipeChatLog.push({
                    role: "ai",
                    text: res.data.answer || "这个问题有点难，再换一种问法？",
                });
            } catch (e) {
                state.recipeChatLog.push({ role: "ai", text: "网络错误，请稍后再试。" });
            }
        };

        const parseMissing = (arr) => {
            if (!arr || !arr.length) return "";
            return "缺：" + arr.join("、");
        };

        const parseTags = (tags) => {
            if (Array.isArray(tags)) return tags;
            try {
                const parsed = JSON.parse(tags);
                return Array.isArray(parsed) ? parsed : [];
            } catch (e) {
                return [];
            }
        };

        return {
            ...toRefs(state),
            showList,
            sendChat,
            doSearch,
            loadDish,
            genToken,
            askRecipe,
            parseMissing,
            parseTags,
        };
    },
});

app.mount("#app");
