// wapair 是一个独立的小工具，编译时被放进 watgbridge 源码树 (cmd/wapair)，
// 与 watgbridge 共用同一个 go.mod / whatsmeow 版本和同一个登录数据库。
//
// 用途：在不启动 watgbridge 的情况下完成 WhatsApp「关联设备」登录。
// 支持两种方式：
//   - 配对码 (--phone 号码)：WhatsApp 手机端「关联设备 → 改用电话号码关联」输入 8 位码
//   - 二维码 (不带 --phone)：输出二维码内容，由管理页面渲染成图片
//
// 所有输出均为一行一个 JSON 对象（stdout），日志写到 stderr，方便管理端解析。
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"watgbridge/state"

	_ "github.com/jackc/pgx/v5"
	_ "github.com/mattn/go-sqlite3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waCompanionReg"
	waWa6 "go.mau.fi/whatsmeow/proto/waWa6"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
)

func emit(event string, fields map[string]any) {
	if fields == nil {
		fields = map[string]any{}
	}
	fields["event"] = event
	fields["time"] = time.Now().Unix()
	b, _ := json.Marshal(fields)
	fmt.Fprintln(os.Stdout, string(b))
}

// pairErr 携带一个稳定的错误码，管理面板据此显示本地化（中/英）的提示。
type pairErr struct {
	code string
	err  error
}

func (e *pairErr) Error() string { return e.code + ": " + e.err.Error() }

func perr(code string, err error) *pairErr { return &pairErr{code: code, err: err} }

func fail(e *pairErr) {
	emit("error", map[string]any{"code": e.code, "error": e.err.Error()})
	os.Exit(1)
}

type stderrLogger struct{ module string }

func (l stderrLogger) logf(level, msg string, args ...any) {
	fmt.Fprintf(os.Stderr, "%s [%s %s] %s\n", time.Now().Format("15:04:05"), l.module, level, fmt.Sprintf(msg, args...))
}
func (l stderrLogger) Warnf(msg string, args ...any)  { l.logf("WARN", msg, args...) }
func (l stderrLogger) Errorf(msg string, args ...any) { l.logf("ERROR", msg, args...) }
func (l stderrLogger) Infof(msg string, args ...any)  { l.logf("INFO", msg, args...) }
func (l stderrLogger) Debugf(string, ...any)          {}
func (l stderrLogger) Sub(module string) waLog.Logger {
	return stderrLogger{module: l.module + "/" + module}
}

// applyDeviceProps 与 watgbridge whatsapp/client.go 中的逻辑保持一致，
// 保证配对时登记的设备类型和 watgbridge 后续使用的一致。
func applyDeviceProps(cfg *state.Config) {
	mode := cfg.WhatsApp.ClientMode
	if mode == "android" || mode == "android_business" {
		store.DeviceProps.Os = proto.String("Android")
		store.DeviceProps.RequireFullSync = proto.Bool(false)
		store.DeviceProps.PlatformType = waCompanionReg.DeviceProps_ANDROID_PHONE.Enum()
		store.DeviceProps.Version = &waCompanionReg.DeviceProps_AppVersion{
			Primary:    proto.Uint32(2),
			Secondary:  proto.Uint32(23),
			Tertiary:   proto.Uint32(9),
			Quaternary: proto.Uint32(0),
		}
		store.DeviceProps.HistorySyncConfig = noHistorySync()

		platform := waWa6.ClientPayload_UserAgent_ANDROID
		if mode == "android_business" {
			platform = waWa6.ClientPayload_UserAgent_SMB_ANDROID
		}
		store.BaseClientPayload.UserAgent.Platform = platform.Enum()
		store.BaseClientPayload.UserAgent.Device = proto.String("SM-G900F")
		store.BaseClientPayload.UserAgent.Manufacturer = proto.String("Samsung")
		store.BaseClientPayload.UserAgent.OsVersion = proto.String("14")
		v := store.GetWAVersion()
		store.BaseClientPayload.UserAgent.AppVersion = &waWa6.ClientPayload_UserAgent_AppVersion{
			Primary:   proto.Uint32(uint32(v[0])),
			Secondary: proto.Uint32(uint32(v[1])),
			Tertiary:  proto.Uint32(uint32(v[2])),
		}
		store.BaseClientPayload.WebInfo = nil
	} else {
		store.DeviceProps.Os = proto.String(cfg.WhatsApp.SessionName)
		store.DeviceProps.RequireFullSync = proto.Bool(false)
		store.DeviceProps.PlatformType = waCompanionReg.DeviceProps_DESKTOP.Enum()
		store.DeviceProps.HistorySyncConfig = noHistorySync()
	}
}

func noHistorySync() *waCompanionReg.DeviceProps_HistorySyncConfig {
	return &waCompanionReg.DeviceProps_HistorySyncConfig{
		FullSyncDaysLimit:              proto.Uint32(0),
		FullSyncSizeMbLimit:            proto.Uint32(0),
		StorageQuotaMb:                 proto.Uint32(0),
		RecentSyncDaysLimit:            proto.Uint32(0),
		SupportCallLogHistory:          proto.Bool(false),
		SupportBotUserAgentChatHistory: proto.Bool(false),
		SupportCagReactionsAndPolls:    proto.Bool(false),
	}
}

func main() {
	configPath := flag.String("config", "config.yaml", "path to watgbridge config file")
	phone := flag.String("phone", "", "phone number for pairing-code login (international format, digits only, e.g. 8613800000000)")
	statusOnly := flag.Bool("status", false, "only print the current login status")
	logout := flag.Bool("logout", false, "log out the current linked device")
	timeout := flag.Duration("timeout", 10*time.Minute, "pairing timeout")
	flag.Parse()

	cfg := state.State.Config
	cfg.SetDefaults()
	cfg.Path = *configPath
	if err := cfg.LoadConfig(); err != nil {
		fail(perr("config_load", err))
	}
	if cfg.WhatsApp.SessionName == "" {
		cfg.WhatsApp.SessionName = "watgbridge"
	}
	if cfg.WhatsApp.LoginDatabase.Type == "" || cfg.WhatsApp.LoginDatabase.URL == "" {
		cfg.WhatsApp.LoginDatabase.Type = "sqlite3"
		cfg.WhatsApp.LoginDatabase.URL = "file:wawebstore.db?_foreign_keys=on"
	}
	applyDeviceProps(cfg)

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigCh; cancel() }()

	log := stderrLogger{module: "wapair"}
	container, err := sqlstore.New(ctx, cfg.WhatsApp.LoginDatabase.Type, cfg.WhatsApp.LoginDatabase.URL, log.Sub("db"))
	if err != nil {
		fail(perr("db_open", err))
	}
	device, err := container.GetFirstDevice(ctx)
	if err != nil {
		fail(perr("db_read", err))
	}
	client := whatsmeow.NewClient(device, log.Sub("client"))

	switch {
	case *statusOnly:
		if device.ID == nil {
			emit("status", map[string]any{"paired": false})
		} else {
			emit("status", map[string]any{"paired": true, "jid": device.ID.String(), "push_name": device.PushName})
		}
		return
	case *logout:
		doLogout(ctx, client, device)
		return
	}

	if device.ID != nil {
		emit("already_paired", map[string]any{"jid": device.ID.String()})
		return
	}

	done := make(chan *pairErr, 1)
	finish := func(err *pairErr) {
		select {
		case done <- err:
		default:
		}
	}
	pairRequested := false
	paired := false

	client.AddEventHandler(func(evt any) {
		switch e := evt.(type) {
		case *events.QR:
			if *phone != "" {
				if pairRequested {
					return
				}
				pairRequested = true
				go func() {
					code, err := client.PairPhone(ctx, *phone, true, whatsmeow.PairClientChrome, "Chrome (Linux)")
					if err != nil {
						finish(perr("pair_code_request", err))
						return
					}
					emit("pair_code", map[string]any{"code": code})
				}()
			} else {
				go rotateQR(ctx, e.Codes, finish)
			}
		case *events.PairSuccess:
			paired = true
			emit("pair_success", map[string]any{"jid": e.ID.String(), "platform": e.Platform, "business_name": e.BusinessName})
		case *events.PairError:
			finish(perr("pair_error", e.Error))
		case *events.Connected:
			if paired {
				finish(nil)
			}
		case *events.LoggedOut:
			finish(perr("logged_out", errors.New("logged out by server")))
		case *events.ClientOutdated:
			finish(perr("client_outdated", errors.New("client outdated")))
		}
	})

	if err := client.Connect(); err != nil {
		fail(perr("connect", err))
	}
	emit("connecting", nil)

	select {
	case err := <-done:
		if err != nil {
			client.Disconnect()
			fail(err)
		}
	case <-ctx.Done():
		client.Disconnect()
		if paired {
			break
		}
		fail(perr("timeout", errors.New("pairing timed out or was cancelled")))
	}

	// 等待一小会儿，让握手后的初始数据写入数据库
	time.Sleep(3 * time.Second)
	jid := ""
	if client.Store.ID != nil {
		jid = client.Store.ID.String()
	}
	client.Disconnect()
	emit("success", map[string]any{"jid": jid, "push_name": client.Store.PushName})
}

func rotateQR(ctx context.Context, codes []string, finish func(*pairErr)) {
	for i, code := range codes {
		wait := 20 * time.Second
		if i == 0 {
			wait = 60 * time.Second
		}
		emit("qr", map[string]any{"code": code, "timeout": int(wait.Seconds())})
		select {
		case <-time.After(wait):
		case <-ctx.Done():
			return
		}
	}
	finish(perr("qr_expired", errors.New("all QR codes expired")))
}

func doLogout(ctx context.Context, client *whatsmeow.Client, device *store.Device) {
	if device.ID == nil {
		emit("logged_out", map[string]any{"code": "not_paired"})
		return
	}
	var logoutErr error
	if err := client.Connect(); err == nil {
		time.Sleep(3 * time.Second)
		logoutErr = client.Logout(ctx)
		client.Disconnect()
	} else {
		logoutErr = err
	}
	if logoutErr != nil {
		// 服务器注销失败时，至少清除本地会话
		if err := device.Delete(ctx); err != nil {
			fail(perr("logout", fmt.Errorf("%v; deleting local session also failed: %v", logoutErr, err)))
		}
		emit("logged_out", map[string]any{"code": "local_only", "error": logoutErr.Error()})
		return
	}
	emit("logged_out", nil)
}
