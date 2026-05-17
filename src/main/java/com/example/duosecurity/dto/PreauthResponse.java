package com.example.duosecurity.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class PreauthResponse {

    private String result;
    private String statusMsg;
    private List<DeviceInfo> devices;

    @Getter
    @Builder
    public static class DeviceInfo {
        private String device;
        private String displayName;
        private String type;
        private List<String> capabilities;
    }
}
