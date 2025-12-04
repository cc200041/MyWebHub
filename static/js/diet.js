const { createApp, reactive, toRefs, computed, onMounted } = Vue;

function todayStr() {
  return new Date().toISOString().split("T")[0];
}

const app = createApp({
  setup() {
    const state = reactive({
      currentUserId: parseInt(localStorage.getItem("fitlife_uid") || "1"),
      currentDate: todayStr(),

      userList: [],
      profile: {
        name: "默认用户",
        height: 170,
        gender: "female",
        age: 25,
        target_weight: 60,
        current_weight: 60,
      },
      dashboard: {
        food_today: 0,
        current_weight: 60,
        bmr: 1800,
        history: [],
      },

      // 记录输入
      activeTab: "search",
      foodQ: "",
      foodList: [],
      tokenInput: "",
      lastPhotoResult: null,

      // 弹窗
      modal: {
        show: false,
        type: "food",
        inputVal: 0,       // 对于 fromFoodDb：吃了多少克
        note: "",
        isSmart: false,
        fromFoodDb: false, // 是否来自食物库
        per100: 0          // 每 100g 热量
      },

      // 用户管理
      showUserModal: false,
      profileForm: {
        height: 170,
        age: 25,
        current_weight_input: 60,
        target_weight: 60,
        gender: "female",
      },

      // 统计数据（给日历用）
      chartDates: [],
      chartValues: [],

      // 小ka 报告
      dailyReportText: "",
    });

    // ---------------- 计算属性 ----------------

    const bmr = computed(() => {
      const w =
        Number(
          state.profile.current_weight ||
            state.profile.target_weight ||
            60
        ) || 60;
      const h = Number(state.profile.height || 170);
      const age = Number(state.profile.age || 25);
      const gender = state.profile.gender || "female";
      let base = 10 * w + 6.25 * h - 5 * age;
      base += gender === "male" ? 5 : -161;
      return Math.round(base);
    });

    const remainingCal = computed(() => {
      const used = Number(state.dashboard.food_today || 0);
      return Math.max(0, Math.round(bmr.value - used));
    });

    const progressWidth = computed(() => {
      if (!bmr.value) return 0;
      const used = Number(state.dashboard.food_today || 0);
      const p = (used / bmr.value) * 100;
      return Math.max(0, Math.min(100, Math.round(p)));
    });

    const bmiStatus = computed(() => {
      const w = Number(state.profile.current_weight || 0);
      const h = Number(state.profile.height || 0);
      if (!w || !h) return "BMI 未知";
      const bmi = w / Math.pow(h / 100, 2);
      if (bmi < 18.5) return `偏瘦 (${bmi.toFixed(1)})`;
      if (bmi < 24) return `正常 (${bmi.toFixed(1)})`;
      if (bmi < 28) return `超重 (${bmi.toFixed(1)})`;
      return `肥胖 (${bmi.toFixed(1)})`;
    });

    // 日历
    const calendarYear = computed(() => new Date().getFullYear());
    const calendarMonth = computed(() => new Date().getMonth() + 1);

    const calendarCells = computed(() => {
      const year = calendarYear.value;
      const month = calendarMonth.value;
      const first = new Date(year, month - 1, 1);
      const firstWeekDay = (first.getDay() + 6) % 7; // 周一=0
      const daysInMonth = new Date(year, month, 0).getDate();

      const map = {};
      state.chartDates.forEach((d, idx) => {
        map[d] = state.chartValues[idx] || 0;
      });

      const cells = [];
      for (let i = 0; i < firstWeekDay; i++) {
        cells.push({ key: "blank-" + i, day: "", bgClass: "bg-transparent" });
      }
      for (let d = 1; d <= daysInMonth; d++) {
        const mm = month.toString().padStart(2, "0");
        const dd = d.toString().padStart(2, "0");
        const ds = `${year}-${mm}-${dd}`;
        const val = map[ds] || 0;

        let bgClass = "bg-white";
        if (val === 0) {
          bgClass = "bg-gray-100";
        } else if (val <= bmr.value) {
          bgClass = "bg-green-300"; // 达标
        } else {
          bgClass = "bg-red-200";   // 超标
        }

        cells.push({ key: ds, day: d, bgClass });
      }
      return cells;
    });

    // ---------------- API ----------------

    const loadUsers = async () => {
      try {
        const res = await axios.get("/api/get_users");
        state.userList = res.data || [];
        if (!state.userList.length) return;
        if (!state.userList.find((u) => u.id === state.currentUserId)) {
          state.currentUserId = state.userList[0].id;
          localStorage.setItem("fitlife_uid", String(state.currentUserId));
        }
      } catch (e) {
        console.error(e);
      }
    };

    const loadDashboard = async () => {
      try {
        const res = await axios.get(
          `/api/get_dashboard?user_id=${state.currentUserId}&date=${state.currentDate}`
        );
        state.dashboard = res.data.data;
        state.profile = res.data.profile || state.profile;
      } catch (e) {
        console.error(e);
      }
    };

    const loadChart = async () => {
      try {
        const res = await axios.get(
          `/api/get_chart_data?user_id=${state.currentUserId}`
        );
        state.chartDates = res.data.dates || [];
        state.chartValues = res.data.values || [];
      } catch (e) {
        console.error(e);
      }
    };

    const searchFood = async () => {
      const q = state.foodQ.trim();
      if (!q) {
        state.foodList = [];
        return;
      }
      try {
        const res = await axios.get(
          `/api/search_food?q=${encodeURIComponent(q)}`
        );
        state.foodList = res.data || [];
      } catch (e) {
        console.error(e);
      }
    };

    // 来自食物库：输入“克数”，自动按每100g kcal 换算
    const quickAddFood = (f) => {
      state.modal = {
        show: true,
        type: "food",
        note: f.name,
        inputVal: 100,        // 默认吃 100g
        isSmart: true,
        fromFoodDb: true,
        per100: Number(f.cal) || 0,
      };
    };

    const parseToken = () => {
      const text = state.tokenInput || "";
      const tokens = text.match(/#HTC:[^#]+#/g) || [];
      if (!tokens.length) {
        alert("没有识别到口令 (#HTC:菜名:热量#)");
        return;
      }
      const t = tokens[0];
      const m = t.match(/^#HTC:(.+):(\d+(?:\.\d+)?)#$/);
      if (!m) {
        alert("口令格式不正确，应为 #HTC:菜名:热量#");
        return;
      }
      const name = m[1];
      const cal = Number(m[2]) || 0;
      state.modal = {
        show: true,
        type: "food",
        note: name,
        inputVal: cal,
        isSmart: true,
        fromFoodDb: false,
        per100: 0,
      };
    };

    const uploadPhoto = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const form = new FormData();
      form.append("photo", file);
      try {
        const res = await axios.post("/api/diet/analyze_food_photo", form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const result = res.data;
        state.lastPhotoResult = { name: result.name, cal: result.cal };
        state.modal = {
          show: true,
          type: "food",
          note: result.name,
          inputVal: result.cal,
          isSmart: true,
          fromFoodDb: false,
          per100: 0,
        };
      } catch (e2) {
        console.error(e2);
        alert("小ka 看不懂这张图，你换个角度或拍近一点试试~");
      }
    };

    const submitLog = async () => {
      let value = 0;
      if (state.modal.type === "food" && state.modal.fromFoodDb && state.modal.per100) {
        const grams = Number(state.modal.inputVal) || 0;
        value = grams * state.modal.per100 / 100;
      } else {
        value = Number(state.modal.inputVal) || 0;
      }

      const payload = {
        user_id: state.currentUserId,
        date: state.currentDate,
        type: state.modal.type || "food",
        value,
        note:
          state.modal.note ||
          (state.modal.type === "weight" ? "体重" : "记录"),
      };
      try {
        await axios.post("/api/add", payload);
        state.modal.show = false;
        await loadDashboard();
        await loadChart();
      } catch (e) {
        console.error(e);
      }
    };

    const deleteLog = async (id) => {
      if (!confirm("确定删除这条记录吗？")) return;
      try {
        await axios.post("/api/delete_log", { id });
        await loadDashboard();
        await loadChart();
      } catch (e) {
        console.error(e);
      }
    };

    const openWeightModal = () => {
      state.modal = {
        show: true,
        type: "weight",
        note: "记录体重",
        inputVal:
          state.profile.current_weight ||
          state.dashboard.current_weight ||
          60,
        isSmart: false,
        fromFoodDb: false,
        per100: 0,
      };
    };

    const onDateChange = async () => {
      await loadDashboard();
    };

    // ---------------- 用户管理 ----------------

    const openUserModal = () => {
      state.profileForm = {
        height: state.profile.height || 170,
        age: state.profile.age || 25,
        current_weight_input:
          state.profile.current_weight ||
          state.dashboard.current_weight ||
          60,
        target_weight: state.profile.target_weight || 60,
        gender: state.profile.gender || "female",
      };
      state.showUserModal = true;
    };

    const saveProfile = async () => {
      const payload = {
        user_id: state.currentUserId,
        height: state.profileForm.height,
        age: state.profileForm.age,
        current_weight_input: state.profileForm.current_weight_input,
        target_weight: state.profileForm.target_weight,
        gender: state.profileForm.gender,
      };
      try {
        await axios.post("/api/save_profile", payload);
        state.showUserModal = false;
        await loadDashboard();
      } catch (e) {
        console.error(e);
      }
    };

    const switchUser = async (u) => {
      state.currentUserId = u.id;
      localStorage.setItem("fitlife_uid", String(u.id));
      await loadDashboard();
      await loadChart();
    };

    const createUser = async () => {
      const name = prompt("请输入新用户昵称：");
      if (!name) return;
      try {
        const res = await axios.post("/api/create_user", { name });
        if (res.data.status === "success") {
          await loadUsers();
          state.currentUserId = res.data.id;
          localStorage.setItem("fitlife_uid", String(state.currentUserId));
          await loadDashboard();
          await loadChart();
        }
      } catch (e) {
        console.error(e);
      }
    };

    const deleteCurrentUser = async () => {
      if (!confirm("删除当前用户以及所有记录？")) return;
      try {
        await axios.post("/api/delete_user", { id: state.currentUserId });
        await loadUsers();
        if (state.userList.length) {
          state.currentUserId = state.userList[0].id;
          localStorage.setItem("fitlife_uid", String(state.currentUserId));
          await loadDashboard();
          await loadChart();
        }
        state.showUserModal = false;
      } catch (e) {
        console.error(e);
      }
    };

    // ---------------- 小ka 报告 ----------------

    const genDailyReport = async () => {
      try {
        const res = await axios.post("/api/diet/daily_report", {
          user_id: state.currentUserId,
        });
        state.dailyReportText = res.data.report;
      } catch (e) {
        console.error(e);
        alert("小ka 今天有点累，报告没整出来~");
      }
    };

    // ---------------- 生命周期 ----------------

    onMounted(async () => {
      await loadUsers();
      await loadDashboard();
      await loadChart();
    });

    return {
      ...toRefs(state),
      bmr,
      remainingCal,
      progressWidth,
      bmiStatus,
      calendarYear,
      calendarMonth,
      calendarCells,
      // methods
      searchFood,
      quickAddFood,
      parseToken,
      uploadPhoto,
      submitLog,
      deleteLog,
      openWeightModal,
      onDateChange,
      openUserModal,
      saveProfile,
      switchUser,
      createUser,
      deleteCurrentUser,
      genDailyReport,
    };
  },
});

app.mount("#app");
