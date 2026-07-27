#ifndef SECUREEYE_CONFIGSCHEMA_HPP
#define SECUREEYE_CONFIGSCHEMA_HPP

#include <string_view>

namespace secureEye::config {

	enum class ValueType {
		Bool,
		Int,
		Float,
		String,
		Enum,
		Path,
		Multiline
	};

	struct ConfigOption {
		std::string_view section;
		std::string_view key;
		ValueType type;

		std::string_view defaultValue;

		bool hasRange = false;
		double min = 0.0;
		double max = 0.0;

		const char* const* enumValues = nullptr;
		const char* note = nullptr;

		std::string_view help;
	};

	inline constexpr const char* const kDetectorBackends[] = { "dlib", "mediapipe", nullptr };
	inline constexpr const char* const kWorkarounds[]      = { "off", "input", "native", nullptr };
	inline constexpr const char* const kRecordingPlugins[] = { "opencv", "ffmpeg", "pyv4l2", nullptr };
	inline constexpr const char* const kDeviceFormats[]    = { "vfwcap", "v4l2", nullptr };
	inline constexpr const char* const kRotateModes[]      = { "0", "1", "2", nullptr };


} // namespace secureEye::config

#endif //SECUREEYE_CONFIGSCHEMA_HPP
