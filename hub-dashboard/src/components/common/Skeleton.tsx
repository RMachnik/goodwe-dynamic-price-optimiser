import React from 'react';

interface SkeletonProps {
    className?: string;
    width?: string | number;
    height?: string | number;
    circle?: boolean;
}

const Skeleton: React.FC<SkeletonProps> = ({
    className = '',
    width,
    height,
    circle
}) => {
    const style: React.CSSProperties = {
        width: width,
        height: height,
        borderRadius: circle ? '50%' : '8px',
    };

    return (
        <div
            className={`skeleton ${className}`}
            style={style}
            aria-hidden="true"
        />
    );
};

export default Skeleton;
