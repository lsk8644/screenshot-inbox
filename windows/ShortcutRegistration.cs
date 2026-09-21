using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

namespace ScreenshotInbox.Windows
{
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    internal struct PropertyKey
    {
        internal Guid FormatId;
        internal uint PropertyId;

        internal PropertyKey(Guid formatId, uint propertyId)
        {
            FormatId = formatId;
            PropertyId = propertyId;
        }
    }

    [StructLayout(LayoutKind.Explicit)]
    internal struct PropVariant : IDisposable
    {
        [FieldOffset(0)]
        private ushort valueType;

        [FieldOffset(8)]
        private IntPtr pointerValue;

        internal static PropVariant FromString(string value)
        {
            return new PropVariant
            {
                valueType = 31,
                pointerValue = Marshal.StringToCoTaskMemUni(value)
            };
        }

        public void Dispose()
        {
            PropVariantClear(ref this);
        }

        [DllImport("ole32.dll")]
        private static extern int PropVariantClear(ref PropVariant value);
    }

    [ComImport]
    [Guid("00021401-0000-0000-C000-000000000046")]
    internal class ShellLink
    {
    }

    [ComImport]
    [Guid("000214F9-0000-0000-C000-000000000046")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IShellLinkW
    {
        uint GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int size,
            IntPtr findData, uint flags);
        uint GetIDList(out IntPtr itemIdList);
        uint SetIDList(IntPtr itemIdList);
        uint GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int size);
        uint SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
        uint GetWorkingDirectory(
            [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder directory, int size);
        uint SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string directory);
        uint GetArguments(
            [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder arguments, int size);
        uint SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
        uint GetHotkey(out short hotkey);
        uint SetHotkey(short hotkey);
        uint GetShowCommand(out uint showCommand);
        uint SetShowCommand(uint showCommand);
        uint GetIconLocation(
            [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder iconPath,
            int size,
            out int iconIndex);
        uint SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string iconPath, int iconIndex);
        uint SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        uint Resolve(IntPtr window, uint flags);
        uint SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }

    [ComImport]
    [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IPropertyStore
    {
        uint GetCount(out uint propertyCount);
        uint GetAt(uint propertyIndex, out PropertyKey key);
        uint GetValue(ref PropertyKey key, IntPtr value);
        uint SetValue(ref PropertyKey key, ref PropVariant value);
        uint Commit();
    }

    public static class ShortcutRegistration
    {
        private static void EnsureSuccess(uint result)
        {
            if (result > 1)
            {
                Marshal.ThrowExceptionForHR(unchecked((int)result));
            }
        }

        public static void Create(
            string shortcutPath,
            string executablePath,
            string arguments,
            string workingDirectory,
            string iconPath,
            int iconIndex,
            string appUserModelId)
        {
            var shellLink = (IShellLinkW)new ShellLink();
            try
            {
                EnsureSuccess(shellLink.SetPath(executablePath));
                EnsureSuccess(shellLink.SetArguments(arguments));
                EnsureSuccess(shellLink.SetWorkingDirectory(workingDirectory));
                EnsureSuccess(shellLink.SetDescription("Screenshot Inbox"));
                EnsureSuccess(shellLink.SetIconLocation(iconPath, iconIndex));

                var propertyStore = (IPropertyStore)shellLink;
                var key = new PropertyKey(
                    new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"),
                    5);
                var value = PropVariant.FromString(appUserModelId);
                try
                {
                    EnsureSuccess(propertyStore.SetValue(ref key, ref value));
                    EnsureSuccess(propertyStore.Commit());
                }
                finally
                {
                    value.Dispose();
                }

                var persistFile = (IPersistFile)shellLink;
                persistFile.Save(shortcutPath, true);
            }
            finally
            {
                Marshal.FinalReleaseComObject(shellLink);
            }
        }
    }
}
